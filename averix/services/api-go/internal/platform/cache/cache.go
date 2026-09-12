// Package cache wraps Redis: the shared cache, the rate limiter and the
// pub/sub fan-out that lets several API instances deliver one WebSocket message.
package cache

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/averix/api/internal/config"
)

type Cache struct {
	client *redis.Client
	prefix string
}

var ErrMiss = errors.New("cache miss")

func Connect(ctx context.Context, cfg config.Redis) (*Cache, error) {
	opts, err := redis.ParseURL(cfg.URL)
	if err != nil {
		return nil, fmt.Errorf("parse REDIS_URL: %w", err)
	}
	opts.MaxRetries = 2
	opts.DialTimeout = 5 * time.Second
	opts.ReadTimeout = 3 * time.Second
	opts.WriteTimeout = 3 * time.Second
	opts.PoolSize = 20

	client := redis.NewClient(opts)
	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := client.Ping(pingCtx).Err(); err != nil {
		_ = client.Close()
		return nil, fmt.Errorf("ping redis: %w", err)
	}
	return &Cache{client: client, prefix: cfg.KeyPrefix}, nil
}

func (c *Cache) Close() error { return c.client.Close() }

func (c *Cache) Ping(ctx context.Context) error { return c.client.Ping(ctx).Err() }

func (c *Cache) key(parts ...string) string {
	k := c.prefix
	for _, p := range parts {
		k += ":" + p
	}
	return k
}

// GetJSON reads and decodes a cached value, returning ErrMiss when absent.
func (c *Cache) GetJSON(ctx context.Context, key string, dst any) error {
	raw, err := c.client.Get(ctx, c.key(key)).Bytes()
	if errors.Is(err, redis.Nil) {
		return ErrMiss
	}
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, dst)
}

func (c *Cache) SetJSON(ctx context.Context, key string, value any, ttl time.Duration) error {
	raw, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return c.client.Set(ctx, c.key(key), raw, ttl).Err()
}

func (c *Cache) Delete(ctx context.Context, keys ...string) error {
	full := make([]string, len(keys))
	for i, k := range keys {
		full[i] = c.key(k)
	}
	return c.client.Del(ctx, full...).Err()
}

// DeletePrefix removes every key under a prefix using SCAN rather than KEYS,
// so invalidating a user's cached views cannot stall the server.
func (c *Cache) DeletePrefix(ctx context.Context, prefix string) error {
	pattern := c.key(prefix) + "*"
	iter := c.client.Scan(ctx, 0, pattern, 200).Iterator()
	batch := make([]string, 0, 200)
	for iter.Next(ctx) {
		batch = append(batch, iter.Val())
		if len(batch) == cap(batch) {
			if err := c.client.Del(ctx, batch...).Err(); err != nil {
				return err
			}
			batch = batch[:0]
		}
	}
	if err := iter.Err(); err != nil {
		return err
	}
	if len(batch) > 0 {
		return c.client.Del(ctx, batch...).Err()
	}
	return nil
}

// Remember returns the cached value, or computes and stores it on a miss.
func Remember[T any](ctx context.Context, c *Cache, key string, ttl time.Duration, load func() (T, error)) (T, error) {
	var out T
	if c != nil {
		if err := c.GetJSON(ctx, key, &out); err == nil {
			return out, nil
		}
	}
	out, err := load()
	if err != nil {
		return out, err
	}
	if c != nil {
		// A cache write failure must not fail the request that already has the
		// answer; it is logged by the caller's logger if it matters.
		_ = c.SetJSON(ctx, key, out, ttl)
	}
	return out, nil
}

// ── Rate limiting ────────────────────────────────────────────────────────────

// Allowance is the result of a rate-limit check.
type Allowance struct {
	Allowed    bool
	Remaining  int
	RetryAfter time.Duration
}

// sliding window counter: one Redis key per (bucket, subject, window), which
// costs one round trip and cannot drift the way a token bucket in process
// memory does across several API instances.
const slidingWindowScript = `
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
`

var slidingWindow = redis.NewScript(slidingWindowScript)

// Allow consumes one unit from the (bucket, subject) window.
func (c *Cache) Allow(ctx context.Context, bucket, subject string, limit int, window time.Duration) (Allowance, error) {
	if limit <= 0 {
		return Allowance{Allowed: true, Remaining: 0}, nil
	}
	key := c.key("rl", bucket, subject)
	res, err := slidingWindow.Run(ctx, c.client, []string{key},
		limit, window.Milliseconds()).Slice()
	if err != nil {
		// Redis being down must not lock everyone out of the product. The
		// request is allowed and the caller logs the degradation; the durable
		// brute-force lockout in Postgres still protects authentication.
		return Allowance{Allowed: true, Remaining: limit}, err
	}
	count, _ := res[0].(int64)
	ttlMS, _ := res[1].(int64)

	remaining := limit - int(count)
	if remaining < 0 {
		remaining = 0
	}
	if int(count) > limit {
		retry := time.Duration(ttlMS) * time.Millisecond
		if retry <= 0 {
			retry = window
		}
		return Allowance{Allowed: false, Remaining: 0, RetryAfter: retry}, nil
	}
	return Allowance{Allowed: true, Remaining: remaining}, nil
}

// Reset clears a limiter window, used after a successful login so one bad
// password does not keep counting against a legitimate user.
func (c *Cache) Reset(ctx context.Context, bucket, subject string) error {
	return c.client.Del(ctx, c.key("rl", bucket, subject)).Err()
}

// ── Locks ───────────────────────────────────────────────────────────────────

// Lock takes a short-lived exclusive lock, returning false if it is held.
// Used to keep one GitHub sync per account and one matcher run per project in
// flight at a time.
func (c *Cache) Lock(ctx context.Context, name string, ttl time.Duration) (release func(), ok bool) {
	key := c.key("lock", name)
	acquired, err := c.client.SetNX(ctx, key, time.Now().UnixNano(), ttl).Result()
	if err != nil || !acquired {
		return func() {}, false
	}
	return func() {
		relCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 3*time.Second)
		defer cancel()
		_ = c.client.Del(relCtx, key).Err()
	}, true
}

// ── Pub/Sub ─────────────────────────────────────────────────────────────────

// Publish fans a message out to every API instance, so a WebSocket client
// connected to one pod receives a message written on another.
func (c *Cache) Publish(ctx context.Context, channel string, payload any) error {
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	return c.client.Publish(ctx, c.key("ps", channel), raw).Err()
}

// Subscribe returns a channel of raw payloads until the context is cancelled.
func (c *Cache) Subscribe(ctx context.Context, channel string) (<-chan []byte, func() error) {
	sub := c.client.Subscribe(ctx, c.key("ps", channel))
	out := make(chan []byte, 64)
	go func() {
		defer close(out)
		ch := sub.Channel()
		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-ch:
				if !ok {
					return
				}
				select {
				case out <- []byte(msg.Payload):
				default:
					// A slow consumer is dropped rather than allowed to block
					// the fan-out for everyone else.
				}
			}
		}
	}()
	return out, sub.Close
}

// Stats exposes Redis pool numbers for the readiness endpoint.
func (c *Cache) Stats() map[string]any {
	s := c.client.PoolStats()
	return map[string]any{
		"hits":        s.Hits,
		"misses":      s.Misses,
		"timeouts":    s.Timeouts,
		"total_conns": s.TotalConns,
		"idle_conns":  s.IdleConns,
	}
}

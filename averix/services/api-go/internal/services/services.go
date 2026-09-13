// Package services owns fixed-price offers: a freelancer publishes "I will
// do X for Y in Z days", a client orders it, and a contract begins without a
// brief, proposals or negotiation.
//
// An order is a real contract from the first second — the same milestones,
// escrow and workspace as a hired project — because a cheaper path that
// skipped those would be the path every dispute arrived through.
package services

import (
	"time"

	"github.com/google/uuid"
)

const (
	StatusDraft    = "draft"
	StatusActive   = "active"
	StatusPaused   = "paused"
	StatusArchived = "archived"
)

// Tier is one of up to three price points. Position 1 is the base tier and
// sets the "from" price the catalogue shows.
type Tier struct {
	ID           uuid.UUID `json:"id"`
	Position     int       `json:"position"`
	Name         string    `json:"name"`
	PriceMinor   int64     `json:"price_minor"`
	PriceDisplay string    `json:"price_display"`
	DeliveryDays int       `json:"delivery_days"`
	Revisions    int       `json:"revisions"`
	Includes     []string  `json:"includes"`
}

type TierInput struct {
	Name         string   `json:"name"`
	PriceMinor   int64    `json:"price_minor"`
	DeliveryDays int      `json:"delivery_days"`
	Revisions    int      `json:"revisions"`
	Includes     []string `json:"includes"`
}

type SkillRef struct {
	Slug   string `json:"slug"`
	Name   string `json:"name"`
	Colour string `json:"colour,omitempty"`
}

type CategoryRef struct {
	Slug string `json:"slug"`
	Name string `json:"name"`
	Path string `json:"path"`
}

// Seller is the freelancer as the catalogue shows them.
type Seller struct {
	UserID            uuid.UUID `json:"user_id"`
	Username          string    `json:"username"`
	FullName          string    `json:"full_name"`
	PhotoURL          string    `json:"photo_url,omitempty"`
	ProfessionalTitle string    `json:"professional_title,omitempty"`
	RatingAvg         *float64  `json:"rating_avg,omitempty"`
	RatingCount       int       `json:"rating_count"`
	ProjectsCompleted int       `json:"projects_completed"`
	Availability      string    `json:"availability"`
}

// Card is the catalogue tile.
type Card struct {
	ID           uuid.UUID   `json:"id"`
	Slug         string      `json:"slug"`
	Title        string      `json:"title"`
	Summary      string      `json:"summary,omitempty"`
	Category     CategoryRef `json:"category"`
	CoverURL     string      `json:"cover_url,omitempty"`
	FromMinor    int64       `json:"from_minor"`
	FromDisplay  string      `json:"from_display"`
	Currency     string      `json:"currency"`
	DeliveryDays int         `json:"delivery_days"`
	OrdersCount  int         `json:"orders_count"`
	RatingAvg    *float64    `json:"rating_avg,omitempty"`
	RatingCount  int         `json:"rating_count"`
	Status       string      `json:"status"`
	Seller       Seller      `json:"seller"`
	CreatedAt    time.Time   `json:"created_at"`
}

// Service is the full page.
type Service struct {
	Card
	Description string     `json:"description"`
	Revisions   int        `json:"revisions"`
	Skills      []SkillRef `json:"skills"`
	Tiers       []Tier     `json:"tiers"`
	// Portfolio items the freelancer attached as examples of this work.
	PortfolioIDs    []uuid.UUID `json:"portfolio_ids"`
	ViewCount       int         `json:"view_count"`
	ModerationState string      `json:"moderation_state,omitempty"`
	UpdatedAt       time.Time   `json:"updated_at"`
	IsOwner         bool        `json:"is_owner,omitempty"`
	// What the caller may do: order it (a client), edit it (the owner).
	CanOrder bool `json:"can_order"`
}

// UpsertRequest is what the editor posts. Every field is required on
// publish, not on save: a draft may be as thin as a title.
type UpsertRequest struct {
	Title        string      `json:"title"`
	Summary      string      `json:"summary"`
	Description  string      `json:"description"`
	CategorySlug string      `json:"category_slug"`
	Currency     string      `json:"currency"`
	Revisions    int         `json:"revisions"`
	Skills       []string    `json:"skills"`
	Tiers        []TierInput `json:"tiers"`
	PortfolioIDs []string    `json:"portfolio_ids"`
	CoverFileID  string      `json:"cover_file_id"`
}

// OrderRequest is what a client sends to buy.
type OrderRequest struct {
	Tier  int    `json:"tier"`
	Brief string `json:"brief"`
	// How the finished work may appear on the freelancer's profile.
	PriceVisibility string `json:"price_visibility"`
}

// Catalogue filters.
type Query struct {
	CategorySlug string
	Text         string
	MinMinor     *int64
	MaxMinor     *int64
	MaxDelivery  *int
	Currency     string
	Sort         string // "relevance" | "newest" | "price_asc" | "price_desc" | "rating" | "popular"
	Offset       int
	Limit        int
	ViewerID     *uuid.UUID
}

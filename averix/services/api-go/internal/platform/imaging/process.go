package imaging

import (
	"bytes"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/gif"
	"image/jpeg"
	"image/png"
	"io"
	"math"

	"github.com/HugoSmits86/nativewebp"
	xdraw "golang.org/x/image/draw"
	_ "golang.org/x/image/webp" // decode-only WebP support
)

// CropShape is how a profile photo is masked on the public profile.
type CropShape string

const (
	Circle  CropShape = "circle"
	Rounded CropShape = "rounded"
)

// Crop is the geometry the client's editor produced, in source-image pixels.
//
// Storing the rectangle rather than the cropped bytes is what lets a developer
// re-frame their photo later without uploading it again, and keeps the original
// available if a larger derivative is ever needed.
type Crop struct {
	X, Y, W, H int
	// 0, 90, 180 or 270, applied before the crop — matching the order the
	// browser editor applies them, so the stored geometry replays exactly.
	Rotation int
	Shape    CropShape
}

func (c Crop) Validate(srcW, srcH int) error {
	switch c.Rotation {
	case 0, 90, 180, 270:
	default:
		return fmt.Errorf("rotation must be 0, 90, 180 or 270 (got %d)", c.Rotation)
	}
	w, h := srcW, srcH
	if c.Rotation == 90 || c.Rotation == 270 {
		w, h = h, w
	}
	if c.W <= 0 || c.H <= 0 {
		return errors.New("crop width and height must be positive")
	}
	if c.X < 0 || c.Y < 0 || c.X+c.W > w || c.Y+c.H > h {
		return fmt.Errorf("crop %dx%d at (%d,%d) falls outside the %dx%d image",
			c.W, c.H, c.X, c.Y, w, h)
	}
	if c.W < minDimension || c.H < minDimension {
		return fmt.Errorf("crop must be at least %dpx on each side", minDimension)
	}
	return nil
}

// Derivative is one rendered size/format pair.
type Derivative struct {
	Label  string
	Width  int
	Height int
	Format Kind
	Bytes  []byte
}

// AvatarSizes are the square sizes the product actually uses:
//
//	 64 — message threads and proposal lists
//	128 — project cards and search results
//	256 — dashboard header and developer cards
//	512 — the public profile portrait, and 2× for the 256 slot
//
// Nothing larger is generated: a profile photo is never displayed above 512px,
// and the original is retained privately if that ever changes.
var AvatarSizes = []struct {
	Label string
	Size  int
}{
	{"xs", 64},
	{"sm", 128},
	{"md", 256},
	{"lg", 512},
}

// Decode reads an image, rejecting anything Inspect would not accept.
//
// The whole file is buffered because the dimension check must happen before
// decoding — a streaming decoder would already have allocated the pixels by
// the time it knew how large they were.
func Decode(r io.Reader, maxBytes int64) (image.Image, Detected, error) {
	if maxBytes <= 0 {
		maxBytes = 20 << 20
	}
	raw, err := io.ReadAll(io.LimitReader(r, maxBytes+1))
	if err != nil {
		return nil, Detected{}, fmt.Errorf("read image: %w", err)
	}
	if int64(len(raw)) > maxBytes {
		return nil, Detected{}, fmt.Errorf("image exceeds %d bytes", maxBytes)
	}

	det, _, err := Inspect(bytes.NewReader(raw))
	if err != nil {
		return nil, det, err
	}
	if err := CheckBomb(det, int64(len(raw))); err != nil {
		return nil, det, err
	}

	var img image.Image
	switch det.Kind {
	case JPEG:
		img, err = jpeg.Decode(bytes.NewReader(raw))
	case PNG:
		img, err = png.Decode(bytes.NewReader(raw))
	case GIF:
		// Only the first frame; an animated avatar is not a thing here.
		img, err = gif.Decode(bytes.NewReader(raw))
	case WebP:
		img, _, err = image.Decode(bytes.NewReader(raw))
	case AVIF, HEIC:
		// Go has no decoder for these without cgo. The phone-camera formats
		// are converted by the browser editor before upload, which already
		// has to decode them to show the crop preview; a direct upload is
		// refused with an explanation rather than silently mangled.
		return nil, det, fmt.Errorf("%w: %s images must be converted before upload",
			ErrUnsupportedFormat, det.Kind.Extension())
	default:
		return nil, det, ErrUnsupportedFormat
	}
	if err != nil {
		return nil, det, fmt.Errorf("decode %s: %w", det.Kind, err)
	}

	// Trust the decoder's bounds over the header, which may have lied.
	b := img.Bounds()
	det.Width, det.Height = b.Dx(), b.Dy()
	return img, det, nil
}

// Transform applies rotation then the crop rectangle.
func Transform(src image.Image, c Crop) (image.Image, error) {
	rotated := rotate(src, c.Rotation)
	b := rotated.Bounds()
	if err := c.Validate(b.Dx(), b.Dy()); err != nil {
		// Validate takes pre-rotation dimensions; re-check against the rotated
		// image so the message matches what the user actually cropped.
		if c.X < 0 || c.Y < 0 || c.X+c.W > b.Dx() || c.Y+c.H > b.Dy() {
			return nil, err
		}
	}
	rect := image.Rect(c.X, c.Y, c.X+c.W, c.Y+c.H).Add(b.Min)
	out := image.NewNRGBA(image.Rect(0, 0, c.W, c.H))
	draw.Draw(out, out.Bounds(), rotated, rect.Min, draw.Src)
	return out, nil
}

func rotate(src image.Image, degrees int) image.Image {
	if degrees == 0 {
		return src
	}
	b := src.Bounds()
	w, h := b.Dx(), b.Dy()
	var out *image.NRGBA
	switch degrees {
	case 90:
		out = image.NewNRGBA(image.Rect(0, 0, h, w))
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				out.Set(h-1-y, x, src.At(b.Min.X+x, b.Min.Y+y))
			}
		}
	case 180:
		out = image.NewNRGBA(image.Rect(0, 0, w, h))
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				out.Set(w-1-x, h-1-y, src.At(b.Min.X+x, b.Min.Y+y))
			}
		}
	case 270:
		out = image.NewNRGBA(image.Rect(0, 0, h, w))
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				out.Set(y, w-1-x, src.At(b.Min.X+x, b.Min.Y+y))
			}
		}
	default:
		return src
	}
	return out
}

// Resize scales to an exact size with a high-quality kernel.
//
// CatmullRom is used rather than a bilinear filter because a profile photo
// scaled from 3000px to 256px with bilinear looks soft, and "don't destroy
// image quality unnecessarily" is a product requirement, not a nicety.
func Resize(src image.Image, w, h int) image.Image {
	out := image.NewNRGBA(image.Rect(0, 0, w, h))
	xdraw.CatmullRom.Scale(out, out.Bounds(), src, src.Bounds(), xdraw.Src, nil)
	return out
}

// FitSquare scales and centre-crops to a square without distorting the subject.
// The image is never stretched: the shorter edge decides the scale and the
// overflow on the longer edge is trimmed evenly.
func FitSquare(src image.Image, size int) image.Image {
	b := src.Bounds()
	w, h := b.Dx(), b.Dy()
	if w == h {
		return Resize(src, size, size)
	}
	side := w
	if h < w {
		side = h
	}
	offX := b.Min.X + (w-side)/2
	offY := b.Min.Y + (h-side)/2
	square := image.NewNRGBA(image.Rect(0, 0, side, side))
	draw.Draw(square, square.Bounds(), src, image.Pt(offX, offY), draw.Src)
	return Resize(square, size, size)
}

// Fit scales to fit inside a box, preserving aspect ratio and never enlarging.
// Used for portfolio screenshots, where the real shape matters.
func Fit(src image.Image, maxW, maxH int) image.Image {
	b := src.Bounds()
	w, h := b.Dx(), b.Dy()
	if w <= maxW && h <= maxH {
		return src
	}
	scale := math.Min(float64(maxW)/float64(w), float64(maxH)/float64(h))
	return Resize(src, int(math.Round(float64(w)*scale)), int(math.Round(float64(h)*scale)))
}

// EncodeOptions controls derivative output.
type EncodeOptions struct {
	JPEGQuality int
	// Background used when flattening transparency into JPEG.
	Background color.NRGBA
}

func DefaultEncodeOptions() EncodeOptions {
	return EncodeOptions{
		JPEGQuality: 82,
		Background:  color.NRGBA{R: 255, G: 255, B: 255, A: 255},
	}
}

// EncodeJPEG writes a JPEG, flattening any transparency first.
func EncodeJPEG(img image.Image, opts EncodeOptions) ([]byte, error) {
	if opts.JPEGQuality == 0 {
		opts = DefaultEncodeOptions()
	}
	flat := flatten(img, opts.Background)
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, flat, &jpeg.Options{Quality: opts.JPEGQuality}); err != nil {
		return nil, fmt.Errorf("encode jpeg: %w", err)
	}
	return buf.Bytes(), nil
}

// EncodePNG writes a lossless PNG, keeping transparency.
func EncodePNG(img image.Image) ([]byte, error) {
	var buf bytes.Buffer
	enc := png.Encoder{CompressionLevel: png.BestCompression}
	if err := enc.Encode(&buf, img); err != nil {
		return nil, fmt.Errorf("encode png: %w", err)
	}
	return buf.Bytes(), nil
}

// EncodeWebP writes a lossless WebP, typically 25-35% smaller than the
// equivalent PNG and supported by every browser AVERIX targets.
func EncodeWebP(img image.Image) ([]byte, error) {
	var buf bytes.Buffer
	if err := nativewebp.Encode(&buf, img, nil); err != nil {
		return nil, fmt.Errorf("encode webp: %w", err)
	}
	return buf.Bytes(), nil
}

func flatten(img image.Image, bg color.NRGBA) image.Image {
	b := img.Bounds()
	out := image.NewNRGBA(b)
	draw.Draw(out, b, &image.Uniform{C: bg}, image.Point{}, draw.Src)
	draw.Draw(out, b, img, b.Min, draw.Over)
	return out
}

// BuildAvatarSet renders every avatar size in WebP and JPEG.
//
// Both formats are produced rather than relying on content negotiation: the
// public profile uses a <picture> element, so the browser picks WebP and the
// JPEG is there for anything that cannot, with no server-side UA sniffing.
func BuildAvatarSet(cropped image.Image, opts EncodeOptions) ([]Derivative, error) {
	var out []Derivative
	for _, s := range AvatarSizes {
		b := cropped.Bounds()
		// Never upscale past the source: a 200px crop rendered at 512 would
		// look worse than the 256 the browser would otherwise scale down.
		size := s.Size
		if shorter := min(b.Dx(), b.Dy()); size > shorter {
			size = shorter
		}
		resized := FitSquare(cropped, size)

		webp, err := EncodeWebP(resized)
		if err != nil {
			return nil, err
		}
		out = append(out, Derivative{
			Label: s.Label, Width: size, Height: size, Format: WebP, Bytes: webp,
		})

		jpg, err := EncodeJPEG(resized, opts)
		if err != nil {
			return nil, err
		}
		out = append(out, Derivative{
			Label: s.Label, Width: size, Height: size, Format: JPEG, Bytes: jpg,
		})

		if size < s.Size {
			// The source cannot fill the larger slots; stop rather than emit
			// duplicate sizes under different labels.
			break
		}
	}
	if len(out) == 0 {
		return nil, errors.New("no avatar derivatives were produced")
	}
	return out, nil
}

// ScreenshotSizes are the widths portfolio galleries request.
var ScreenshotSizes = []struct {
	Label  string
	Width  int
	Height int
}{
	{"thumb", 480, 480},
	{"card", 960, 960},
	{"full", 1920, 1920},
}

// BuildScreenshotSet renders portfolio screenshots at gallery widths, keeping
// each image's real aspect ratio.
func BuildScreenshotSet(src image.Image, opts EncodeOptions) ([]Derivative, error) {
	var out []Derivative
	srcW := src.Bounds().Dx()
	for _, s := range ScreenshotSizes {
		if s.Width > srcW && len(out) > 0 {
			break
		}
		resized := Fit(src, s.Width, s.Height)
		b := resized.Bounds()

		webp, err := EncodeWebP(resized)
		if err != nil {
			return nil, err
		}
		out = append(out, Derivative{
			Label: s.Label, Width: b.Dx(), Height: b.Dy(), Format: WebP, Bytes: webp,
		})

		jpg, err := EncodeJPEG(resized, opts)
		if err != nil {
			return nil, err
		}
		out = append(out, Derivative{
			Label: s.Label, Width: b.Dx(), Height: b.Dy(), Format: JPEG, Bytes: jpg,
		})
	}
	return out, nil
}

// AverageColour returns the mean colour as a hex string, used as the blur-up
// placeholder so a loading image is a tinted block rather than a white flash.
func AverageColour(img image.Image) string {
	b := img.Bounds()
	if b.Empty() {
		return "#EFEFF2"
	}
	// Sample a grid rather than every pixel: 400 samples is indistinguishable
	// from a full scan for an average and is constant-time for any input size.
	const steps = 20
	var rs, gs, bs, n uint64
	for iy := 0; iy < steps; iy++ {
		for ix := 0; ix < steps; ix++ {
			x := b.Min.X + b.Dx()*ix/steps
			y := b.Min.Y + b.Dy()*iy/steps
			r, g, bl, a := img.At(x, y).RGBA()
			if a == 0 {
				continue
			}
			rs += uint64(r >> 8)
			gs += uint64(g >> 8)
			bs += uint64(bl >> 8)
			n++
		}
	}
	if n == 0 {
		return "#EFEFF2"
	}
	return fmt.Sprintf("#%02X%02X%02X", rs/n, gs/n, bs/n)
}

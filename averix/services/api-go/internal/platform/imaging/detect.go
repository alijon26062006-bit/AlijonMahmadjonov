// Package imaging validates uploaded images server-side and produces the
// derivatives the product serves.
package imaging

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"strings"
)

// Kind is a format AVERIX accepts for an upload.
type Kind string

const (
	JPEG Kind = "image/jpeg"
	PNG  Kind = "image/png"
	WebP Kind = "image/webp"
	GIF  Kind = "image/gif"
	AVIF Kind = "image/avif"
	HEIC Kind = "image/heic"
)

func (k Kind) Extension() string {
	switch k {
	case JPEG:
		return "jpg"
	case PNG:
		return "png"
	case WebP:
		return "webp"
	case GIF:
		return "gif"
	case AVIF:
		return "avif"
	case HEIC:
		return "heic"
	}
	return "bin"
}

var (
	ErrUnsupportedFormat = errors.New("unsupported image format")
	ErrNotAnImage        = errors.New("file is not an image")
	ErrDimensions        = errors.New("image dimensions are outside the accepted range")
	// A small file that claims enormous dimensions is a decompression bomb:
	// decoding it would allocate gigabytes.
	ErrDecompressionBomb = errors.New("image dimensions are implausible for its file size")
)

// Detected is what the server concluded about an upload, independent of what
// the client claimed.
type Detected struct {
	Kind   Kind
	Width  int
	Height int
	// True when the format supports transparency, which decides whether a
	// derivative is flattened onto a background.
	HasAlpha bool
	// True for an animated GIF or WebP; only the first frame is used.
	Animated bool
}

const (
	// Enough bytes for every header this package reads.
	headerBytes  = 64 * 1024
	minDimension = 16
	maxDimension = 12000
	// Above roughly this many pixels per byte, the file is a bomb rather than
	// a photograph. A 1×1 PNG is ~70 bytes, a real photo is well under 1.
	maxPixelsPerByte = 300
)

// Inspect identifies an image from its actual bytes.
//
// The browser-supplied Content-Type and the filename extension are both
// ignored here: an attacker controls both, and "avatar.jpg" containing PHP is
// the oldest upload bug there is. The magic bytes are the only input.
func Inspect(r io.Reader) (Detected, []byte, error) {
	head := make([]byte, headerBytes)
	n, err := io.ReadFull(r, head)
	if err != nil && !errors.Is(err, io.ErrUnexpectedEOF) && !errors.Is(err, io.EOF) {
		return Detected{}, nil, fmt.Errorf("read image header: %w", err)
	}
	head = head[:n]
	if len(head) < 12 {
		return Detected{}, head, ErrNotAnImage
	}

	det, err := identify(head)
	if err != nil {
		return Detected{}, head, err
	}
	if det.Width < minDimension || det.Height < minDimension {
		return det, head, fmt.Errorf("%w: %dx%d is smaller than %dpx",
			ErrDimensions, det.Width, det.Height, minDimension)
	}
	if det.Width > maxDimension || det.Height > maxDimension {
		return det, head, fmt.Errorf("%w: %dx%d exceeds %dpx",
			ErrDimensions, det.Width, det.Height, maxDimension)
	}
	return det, head, nil
}

func identify(b []byte) (Detected, error) {
	switch {
	case bytes.HasPrefix(b, []byte{0xFF, 0xD8, 0xFF}):
		w, h, err := jpegDimensions(b)
		return Detected{Kind: JPEG, Width: w, Height: h}, err

	case bytes.HasPrefix(b, []byte("\x89PNG\r\n\x1a\n")):
		if len(b) < 33 {
			return Detected{}, ErrNotAnImage
		}
		// IHDR is always the first chunk: length(4) type(4) width(4) height(4)
		w := int(binary.BigEndian.Uint32(b[16:20]))
		h := int(binary.BigEndian.Uint32(b[20:24]))
		colourType := b[25]
		// 4 = greyscale+alpha, 6 = truecolour+alpha, 3 = palette (may have tRNS)
		hasAlpha := colourType == 4 || colourType == 6 ||
			(colourType == 3 && bytes.Contains(b, []byte("tRNS")))
		animated := bytes.Contains(b, []byte("acTL")) // APNG
		return Detected{Kind: PNG, Width: w, Height: h, HasAlpha: hasAlpha, Animated: animated}, nil

	case bytes.HasPrefix(b, []byte("RIFF")) && len(b) > 15 && bytes.Equal(b[8:12], []byte("WEBP")):
		return webpDimensions(b)

	case bytes.HasPrefix(b, []byte("GIF87a")), bytes.HasPrefix(b, []byte("GIF89a")):
		if len(b) < 10 {
			return Detected{}, ErrNotAnImage
		}
		w := int(binary.LittleEndian.Uint16(b[6:8]))
		h := int(binary.LittleEndian.Uint16(b[8:10]))
		// More than one Graphic Control Extension means animation.
		animated := bytes.Count(b, []byte{0x21, 0xF9, 0x04}) > 1
		return Detected{Kind: GIF, Width: w, Height: h, HasAlpha: true, Animated: animated}, nil

	case len(b) > 12 && bytes.Equal(b[4:8], []byte("ftyp")):
		brand := string(b[8:12])
		switch {
		case strings.HasPrefix(brand, "avif"), strings.HasPrefix(brand, "avis"):
			w, h, err := isoDimensions(b)
			return Detected{Kind: AVIF, Width: w, Height: h, HasAlpha: true}, err
		case strings.HasPrefix(brand, "heic"), strings.HasPrefix(brand, "heix"),
			strings.HasPrefix(brand, "hevc"), strings.HasPrefix(brand, "mif1"),
			strings.HasPrefix(brand, "msf1"):
			w, h, err := isoDimensions(b)
			return Detected{Kind: HEIC, Width: w, Height: h}, err
		}
		return Detected{}, fmt.Errorf("%w: ISO base media brand %q", ErrUnsupportedFormat, brand)

	// Formats worth naming explicitly, so the error tells the user something
	// useful instead of "unsupported".
	case bytes.HasPrefix(b, []byte("BM")):
		return Detected{}, fmt.Errorf("%w: BMP", ErrUnsupportedFormat)
	case bytes.HasPrefix(b, []byte("II*\x00")), bytes.HasPrefix(b, []byte("MM\x00*")):
		return Detected{}, fmt.Errorf("%w: TIFF", ErrUnsupportedFormat)
	case bytes.Contains(b[:min(len(b), 1024)], []byte("<svg")):
		// SVG is XML that can carry script; it is never accepted as a photo.
		return Detected{}, fmt.Errorf("%w: SVG images can't be used here", ErrUnsupportedFormat)
	case bytes.HasPrefix(b, []byte("%PDF")):
		return Detected{}, fmt.Errorf("%w: PDF", ErrNotAnImage)
	}
	return Detected{}, ErrNotAnImage
}

// CheckBomb rejects a file whose claimed pixel count is implausible for its size.
func CheckBomb(det Detected, byteSize int64) error {
	if byteSize <= 0 {
		return nil
	}
	pixels := int64(det.Width) * int64(det.Height)
	if pixels/byteSize > maxPixelsPerByte {
		return fmt.Errorf("%w: %dx%d in %d bytes", ErrDecompressionBomb, det.Width, det.Height, byteSize)
	}
	return nil
}

// jpegDimensions walks the segment chain to the first Start-Of-Frame marker.
func jpegDimensions(b []byte) (int, int, error) {
	i := 2
	for i+9 < len(b) {
		if b[i] != 0xFF {
			i++
			continue
		}
		marker := b[i+1]
		// Padding and standalone markers carry no length.
		if marker == 0xFF {
			i++
			continue
		}
		if marker == 0x01 || (marker >= 0xD0 && marker <= 0xD9) {
			i += 2
			continue
		}
		length := int(binary.BigEndian.Uint16(b[i+2 : i+4]))
		if length < 2 {
			return 0, 0, ErrNotAnImage
		}
		// SOF0..SOF15, excluding the DHT/JPG/DAC markers interleaved with them.
		isSOF := marker >= 0xC0 && marker <= 0xCF &&
			marker != 0xC4 && marker != 0xC8 && marker != 0xCC
		if isSOF {
			if i+9 >= len(b) {
				return 0, 0, ErrNotAnImage
			}
			h := int(binary.BigEndian.Uint16(b[i+5 : i+7]))
			w := int(binary.BigEndian.Uint16(b[i+7 : i+9]))
			return w, h, nil
		}
		i += 2 + length
	}
	return 0, 0, fmt.Errorf("%w: no JPEG frame header found", ErrNotAnImage)
}

// webpDimensions reads the VP8/VP8L/VP8X sub-chunk.
func webpDimensions(b []byte) (Detected, error) {
	if len(b) < 30 {
		return Detected{}, ErrNotAnImage
	}
	switch string(b[12:16]) {
	case "VP8 ": // lossy
		// Frame header: 3 bytes tag, 3 bytes start code, then 16-bit dimensions.
		if len(b) < 30 {
			return Detected{}, ErrNotAnImage
		}
		w := int(binary.LittleEndian.Uint16(b[26:28]) & 0x3FFF)
		h := int(binary.LittleEndian.Uint16(b[28:30]) & 0x3FFF)
		return Detected{Kind: WebP, Width: w, Height: h}, nil
	case "VP8L": // lossless
		if len(b) < 25 {
			return Detected{}, ErrNotAnImage
		}
		bits := binary.LittleEndian.Uint32(b[21:25])
		w := int(bits&0x3FFF) + 1
		h := int((bits>>14)&0x3FFF) + 1
		hasAlpha := (bits>>28)&1 == 1
		return Detected{Kind: WebP, Width: w, Height: h, HasAlpha: hasAlpha}, nil
	case "VP8X": // extended
		if len(b) < 30 {
			return Detected{}, ErrNotAnImage
		}
		flags := b[20]
		w := int(uint32(b[24])|uint32(b[25])<<8|uint32(b[26])<<16) + 1
		h := int(uint32(b[27])|uint32(b[28])<<8|uint32(b[29])<<16) + 1
		return Detected{
			Kind:     WebP,
			Width:    w,
			Height:   h,
			HasAlpha: flags&0x10 != 0,
			Animated: flags&0x02 != 0,
		}, nil
	}
	return Detected{}, fmt.Errorf("%w: unknown WebP sub-chunk", ErrNotAnImage)
}

// isoDimensions finds the primary item's ispe box in an AVIF/HEIC file.
//
// Only the header window is searched, which is enough for the files phones
// produce. When it is not found the caller still has a valid format and can
// decode to learn the size; returning zero here is not an error.
func isoDimensions(b []byte) (int, int, error) {
	idx := bytes.Index(b, []byte("ispe"))
	if idx < 0 || idx+12 > len(b) {
		return 0, 0, nil
	}
	// ispe: version(1) flags(3) width(4) height(4)
	w := int(binary.BigEndian.Uint32(b[idx+4+4 : idx+4+8]))
	h := int(binary.BigEndian.Uint32(b[idx+4+8 : idx+4+12]))
	return w, h, nil
}

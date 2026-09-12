package imaging

import (
	"bytes"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"strings"
	"testing"
)

func sampleImage(w, h int) *image.NRGBA {
	m := image.NewNRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			m.Set(x, y, color.NRGBA{
				R: uint8((x * 255) / max(w-1, 1)),
				G: uint8((y * 255) / max(h-1, 1)),
				B: 0x70,
				A: 255,
			})
		}
	}
	return m
}

func encodeJPEG(t *testing.T, w, h int) []byte {
	t.Helper()
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, sampleImage(w, h), &jpeg.Options{Quality: 90}); err != nil {
		t.Fatalf("encode fixture: %v", err)
	}
	return buf.Bytes()
}

func encodePNG(t *testing.T, w, h int) []byte {
	t.Helper()
	var buf bytes.Buffer
	if err := png.Encode(&buf, sampleImage(w, h)); err != nil {
		t.Fatalf("encode fixture: %v", err)
	}
	return buf.Bytes()
}

func TestInspectReadsRealDimensions(t *testing.T) {
	cases := []struct {
		name string
		data []byte
		kind Kind
		w, h int
	}{
		{"jpeg", encodeJPEG(t, 640, 480), JPEG, 640, 480},
		{"jpeg portrait", encodeJPEG(t, 300, 900), JPEG, 300, 900},
		{"png", encodePNG(t, 512, 512), PNG, 512, 512},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			det, _, err := Inspect(bytes.NewReader(c.data))
			if err != nil {
				t.Fatalf("Inspect: %v", err)
			}
			if det.Kind != c.kind {
				t.Errorf("Kind = %q, want %q", det.Kind, c.kind)
			}
			if det.Width != c.w || det.Height != c.h {
				t.Errorf("dimensions = %dx%d, want %dx%d", det.Width, det.Height, c.w, c.h)
			}
		})
	}
}

// The whole point of server-side detection: an attacker controls the filename
// and the Content-Type, so neither is consulted. These payloads are all named
// like images and are all refused.
func TestInspectRejectsDisguisedUploads(t *testing.T) {
	cases := []struct {
		name string
		data []byte
	}{
		{"php webshell", []byte("<?php system($_GET['c']); ?>")},
		{"php after jpeg magic", append([]byte{0xFF, 0xD8, 0xFF, 0xE0}, []byte("<?php system($_GET['c']); ?>")...)},
		{"html with script", []byte("<html><body><script>alert(document.cookie)</script></body></html>")},
		{"svg with onload", []byte(`<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect/></svg>`)},
		{"svg no prolog", []byte(`<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>`)},
		{"elf binary", []byte("\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00")},
		{"windows exe", []byte("MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff")},
		{"zip archive", []byte("PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00\x00\x00")},
		{"pdf", []byte("%PDF-1.7\n1 0 obj\n<<>>\nendobj\n")},
		{"shell script", []byte("#!/bin/sh\nrm -rf /\n")},
		{"empty", []byte{}},
		{"too short", []byte{0xFF, 0xD8}},
		{"bmp", append([]byte("BM"), make([]byte, 60)...)},
		{"tiff", append([]byte("II*\x00"), make([]byte, 60)...)},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if det, _, err := Inspect(bytes.NewReader(c.data)); err == nil {
				t.Fatalf("accepted a disguised upload as %s %dx%d", det.Kind, det.Width, det.Height)
			}
		})
	}
}

// A JPEG with an appended PHP payload still decodes as a JPEG, which is exactly
// why the pipeline re-encodes every derivative rather than storing the upload.
// The re-encoded output must carry none of the original bytes.
func TestReencodingStripsAppendedPayload(t *testing.T) {
	payload := []byte("<?php system($_GET['cmd']); ?>")
	polyglot := append(encodeJPEG(t, 200, 200), payload...)

	img, det, err := Decode(bytes.NewReader(polyglot), 10<<20)
	if err != nil {
		t.Fatalf("a valid JPEG with trailing bytes should still decode: %v", err)
	}
	if det.Kind != JPEG {
		t.Fatalf("Kind = %q, want image/jpeg", det.Kind)
	}
	out, err := EncodeJPEG(FitSquare(img, 128), DefaultEncodeOptions())
	if err != nil {
		t.Fatalf("EncodeJPEG: %v", err)
	}
	if bytes.Contains(out, payload) {
		t.Error("the re-encoded derivative still contains the appended payload")
	}
	if bytes.Contains(out, []byte("<?php")) {
		t.Error("the re-encoded derivative still contains PHP markers")
	}
}

func TestCheckBombRejectsImplausibleDimensions(t *testing.T) {
	// A 40,000 × 40,000 "image" in 800 bytes is 1.6 billion pixels of RAM.
	bomb := Detected{Kind: PNG, Width: 40000, Height: 40000}
	if err := CheckBomb(bomb, 800); err == nil {
		t.Error("a decompression bomb was accepted")
	}
	real := Detected{Kind: JPEG, Width: 3000, Height: 2000}
	if err := CheckBomb(real, 1_400_000); err != nil {
		t.Errorf("a plausible photograph was rejected: %v", err)
	}
}

func TestInspectRejectsOutOfRangeDimensions(t *testing.T) {
	if _, _, err := Inspect(bytes.NewReader(encodePNG(t, 8, 8))); err == nil {
		t.Error("an 8x8 image should be rejected as too small for a profile photo")
	}
}

func TestCropValidation(t *testing.T) {
	cases := []struct {
		name    string
		crop    Crop
		wantErr bool
	}{
		{"inside bounds", Crop{X: 10, Y: 10, W: 200, H: 200}, false},
		{"exactly the image", Crop{X: 0, Y: 0, W: 400, H: 300}, false},
		{"negative origin", Crop{X: -5, Y: 0, W: 100, H: 100}, true},
		{"overflows right", Crop{X: 350, Y: 0, W: 100, H: 100}, true},
		{"overflows bottom", Crop{X: 0, Y: 250, W: 100, H: 100}, true},
		{"zero size", Crop{X: 0, Y: 0, W: 0, H: 0}, true},
		{"negative size", Crop{X: 0, Y: 0, W: -10, H: -10}, true},
		{"below minimum", Crop{X: 0, Y: 0, W: 8, H: 8}, true},
		{"bad rotation", Crop{X: 0, Y: 0, W: 100, H: 100, Rotation: 45}, true},
		{"rotated 90 swaps bounds", Crop{X: 0, Y: 0, W: 300, H: 400, Rotation: 90}, false},
		{"rotated 90 using unrotated bounds", Crop{X: 0, Y: 0, W: 400, H: 300, Rotation: 90}, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			err := c.crop.Validate(400, 300)
			if c.wantErr && err == nil {
				t.Errorf("Validate(%+v) should have failed", c.crop)
			}
			if !c.wantErr && err != nil {
				t.Errorf("Validate(%+v) failed: %v", c.crop, err)
			}
		})
	}
}

func TestTransformCropsAndRotates(t *testing.T) {
	src := sampleImage(400, 300)

	out, err := Transform(src, Crop{X: 50, Y: 25, W: 200, H: 150})
	if err != nil {
		t.Fatalf("Transform: %v", err)
	}
	if b := out.Bounds(); b.Dx() != 200 || b.Dy() != 150 {
		t.Errorf("cropped to %dx%d, want 200x150", b.Dx(), b.Dy())
	}

	rotated, err := Transform(src, Crop{X: 0, Y: 0, W: 300, H: 400, Rotation: 90})
	if err != nil {
		t.Fatalf("Transform rotated: %v", err)
	}
	if b := rotated.Bounds(); b.Dx() != 300 || b.Dy() != 400 {
		t.Errorf("rotated crop is %dx%d, want 300x400", b.Dx(), b.Dy())
	}
}

// "Do not stretch the image" is a product requirement. A wide source cropped
// to a square must be centre-trimmed, not squashed.
func TestFitSquareDoesNotDistort(t *testing.T) {
	wide := sampleImage(800, 200)
	out := FitSquare(wide, 256)
	b := out.Bounds()
	if b.Dx() != 256 || b.Dy() != 256 {
		t.Fatalf("FitSquare produced %dx%d, want 256x256", b.Dx(), b.Dy())
	}
	// The centre column of a horizontal gradient is mid-grey in red. If the
	// image had been stretched rather than trimmed, the left edge would be 0.
	leftEdge, _, _, _ := out.At(2, 128).RGBA()
	if leftEdge>>8 < 40 {
		t.Errorf("left edge red = %d; the image looks stretched rather than centre-cropped", leftEdge>>8)
	}
}

func TestFitNeverEnlarges(t *testing.T) {
	small := sampleImage(300, 200)
	out := Fit(small, 1920, 1920)
	if b := out.Bounds(); b.Dx() != 300 || b.Dy() != 200 {
		t.Errorf("Fit enlarged a small image to %dx%d", b.Dx(), b.Dy())
	}
}

func TestBuildAvatarSetProducesBothFormats(t *testing.T) {
	set, err := BuildAvatarSet(sampleImage(1024, 1024), DefaultEncodeOptions())
	if err != nil {
		t.Fatalf("BuildAvatarSet: %v", err)
	}
	formats := map[Kind]int{}
	labels := map[string]bool{}
	for _, d := range set {
		if len(d.Bytes) == 0 {
			t.Errorf("derivative %s/%s is empty", d.Label, d.Format)
		}
		formats[d.Format]++
		labels[d.Label] = true
	}
	if formats[WebP] == 0 || formats[JPEG] == 0 {
		t.Errorf("expected both WebP and JPEG derivatives, got %v", formats)
	}
	for _, s := range AvatarSizes {
		if !labels[s.Label] {
			t.Errorf("missing the %s (%dpx) avatar size", s.Label, s.Size)
		}
	}
	// WebP should beat JPEG on a synthetic gradient; if it does not, the
	// encoder is not doing its job and serving it would be pointless.
	var webpTotal, jpegTotal int
	for _, d := range set {
		if d.Format == WebP {
			webpTotal += len(d.Bytes)
		} else {
			jpegTotal += len(d.Bytes)
		}
	}
	t.Logf("avatar set: webp %d bytes, jpeg %d bytes", webpTotal, jpegTotal)
}

// A small crop must not be upscaled into the larger slots.
func TestBuildAvatarSetDoesNotUpscale(t *testing.T) {
	set, err := BuildAvatarSet(sampleImage(150, 150), DefaultEncodeOptions())
	if err != nil {
		t.Fatalf("BuildAvatarSet: %v", err)
	}
	for _, d := range set {
		if d.Width > 150 {
			t.Errorf("derivative %s is %dpx, upscaled beyond the 150px source", d.Label, d.Width)
		}
	}
}

func TestAverageColourIsAHexTriplet(t *testing.T) {
	got := AverageColour(sampleImage(64, 64))
	if len(got) != 7 || !strings.HasPrefix(got, "#") {
		t.Fatalf("AverageColour = %q, want a #RRGGBB string", got)
	}
	for _, r := range got[1:] {
		if !strings.ContainsRune("0123456789ABCDEF", r) {
			t.Fatalf("AverageColour = %q contains a non-hex character", got)
		}
	}
}

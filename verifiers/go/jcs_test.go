package main

import "testing"

// Independent Go-side anchor for the ES6 Number::toString edges + RFC 8785 structure — pinned against
// the SAME known JavaScript outputs as the Python tests, so each implementation stands on its own.
// (Control-char escaping is anchored comprehensively by the crosslang diff against canonical.py.)
func TestES6Numbers(t *testing.T) {
	cases := map[float64]string{
		0: "0", 4.5: "4.5", 0.002: "0.002",
		1e30: "1e+30", 1e-27: "1e-27",
		1e20: "100000000000000000000", 1e21: "1e+21",
		1e-6: "0.000001", 1e-7: "1e-7",
		123456789.0: "123456789",
	}
	for x, want := range cases {
		got, err := es6Number(x)
		if err != nil || got != want {
			t.Errorf("es6Number(%v) = %q (err %v), want %q", x, got, err, want)
		}
	}
}

func TestCanonicalStructureAndSorting(t *testing.T) {
	// keys sort by UTF-16 code units: 'é' (U+00E9) sorts AFTER 'z'
	obj := map[string]interface{}{"z": jsonInt{"1"}, "a": jsonInt{"2"}, "b": jsonInt{"3"}, "é": jsonInt{"4"}}
	got, _ := Canonicalize(obj)
	want := `{"a":2,"b":3,"z":1,"é":4}`
	if got != want {
		t.Errorf("sorting: got %q want %q", got, want)
	}
}

func TestEscaping(t *testing.T) {
	cases := []struct{ in, want string }{
		{`"`, `"\""`},
		{`\`, `"\\"`},
		{"\n", `"\n"`},
		{"/", `"/"`}, // forward slash NOT escaped
		{"€", `"€"`}, // non-ASCII literal
	}
	for _, c := range cases {
		got, _ := Canonicalize(c.in)
		if got != c.want {
			t.Errorf("escape(%q) = %q want %q", c.in, got, c.want)
		}
	}
}

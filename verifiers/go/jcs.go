// An INDEPENDENT Go implementation of RFC 8785 JSON Canonicalization (the external anchor, meta-rule
// M3, for cyberware's single canonical-bytes path). Written to reproduce infra/cwp/canonical.py
// byte-for-byte; any divergence between the two is a conformance bug in one of them, which is the
// whole point of a second implementation.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math"
	"math/big"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

// es6Number formats a finite float64 exactly as ECMAScript Number::toString (RFC 8785 §3.2.2.3),
// using the shortest round-trip decimal and the positional rules. Mirrors canonical.py's _es6_number.
func es6Number(x float64) (string, error) {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return "", fmt.Errorf("NaN/Infinity is not a valid JSON number")
	}
	if x == 0 {
		return "0", nil // JCS folds -0 to "0"
	}
	neg := x < 0
	if neg {
		x = -x
	}
	es := strconv.FormatFloat(x, 'e', -1, 64) // shortest, e.g. "2e-03", "1e+30", "3.333e+08"
	ei := strings.IndexByte(es, 'e')
	exp, _ := strconv.Atoi(es[ei+1:])
	digits := strings.Replace(es[:ei], ".", "", 1)
	digits = strings.TrimRight(digits, "0")
	if digits == "" {
		digits = "0"
	}
	k := len(digits)
	n := exp + 1 // value = digits[0].digits[1:] × 10^exp → leading-digit position n = exp+1
	var body string
	switch {
	case k <= n && n <= 21:
		body = digits + strings.Repeat("0", n-k)
	case 0 < n && n <= 21:
		body = digits[:n] + "." + digits[n:]
	case -6 < n && n <= 0:
		body = "0." + strings.Repeat("0", -n) + digits
	default:
		m := digits[:1]
		if k > 1 {
			m += "." + digits[1:]
		}
		e := n - 1
		sign := "+"
		if e < 0 {
			sign = "-"
			e = -e
		}
		body = m + "e" + sign + strconv.Itoa(e)
	}
	if neg {
		return "-" + body, nil
	}
	return body, nil
}

func escape(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, ch := range s {
		switch {
		case ch == '"':
			b.WriteString(`\"`)
		case ch == '\\':
			b.WriteString(`\\`)
		case ch == 0x08:
			b.WriteString(`\b`)
		case ch == 0x09:
			b.WriteString(`\t`)
		case ch == 0x0A:
			b.WriteString(`\n`)
		case ch == 0x0C:
			b.WriteString(`\f`)
		case ch == 0x0D:
			b.WriteString(`\r`)
		case ch < 0x20:
			b.WriteString(fmt.Sprintf(`\u%04x`, ch))
		default:
			b.WriteRune(ch)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// utf16Less compares two strings by their UTF-16 code-unit sequences (RFC 8785 §3.2.3 key ordering).
func utf16Less(a, b string) bool {
	ua, ub := utf16.Encode([]rune(a)), utf16.Encode([]rune(b))
	for i := 0; i < len(ua) && i < len(ub); i++ {
		if ua[i] != ub[i] {
			return ua[i] < ub[i]
		}
	}
	return len(ua) < len(ub)
}

// Canonicalize renders a decoded JSON value (the shapes encoding/json with UseNumber produces, plus
// json.Number classified into int/float exactly as Python's json does) into its JCS form.
func Canonicalize(v interface{}) (string, error) {
	switch t := v.(type) {
	case nil:
		return "null", nil
	case bool:
		if t {
			return "true", nil
		}
		return "false", nil
	case string:
		return escape(t), nil
	case jsonInt:
		return t.s, nil // an integer token, preserved exactly
	case float64:
		return es6Number(t)
	case []interface{}:
		parts := make([]string, len(t))
		for i, e := range t {
			s, err := Canonicalize(e)
			if err != nil {
				return "", err
			}
			parts[i] = s
		}
		return "[" + strings.Join(parts, ",") + "]", nil
	case map[string]interface{}:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })
		parts := make([]string, len(keys))
		for i, k := range keys {
			s, err := Canonicalize(t[k])
			if err != nil {
				return "", err
			}
			parts[i] = escape(k) + ":" + s
		}
		return "{" + strings.Join(parts, ",") + "}", nil
	default:
		return "", fmt.Errorf("not JSON-serializable: %T", v)
	}
}

// jsonInt is an integer JSON token preserved exactly (Python's json yields an arbitrary-precision int
// for a number with no '.'/'e'/'E'; we match that — never round-tripping a big int through float64).
type jsonInt struct{ s string }

// Digest is sha256 over the canonical UTF-8 bytes.
func Digest(v interface{}) (string, error) {
	c, err := Canonicalize(v)
	if err != nil {
		return "", err
	}
	h := sha256.Sum256([]byte(c))
	return hex.EncodeToString(h[:]), nil
}

// normalizeNumber classifies a json.Number token the way Python's json module does: an integer (no
// '.', 'e', 'E') stays exact via big.Int; anything else is a float64.
func normalizeNumber(tok string) (interface{}, error) {
	if !strings.ContainsAny(tok, ".eE") {
		z := new(big.Int)
		if _, ok := z.SetString(tok, 10); ok {
			return jsonInt{z.String()}, nil
		}
	}
	f, err := strconv.ParseFloat(tok, 64)
	if err != nil {
		return nil, err
	}
	return f, nil
}

// Command jcs-verify reads a corpus of JSON inputs and emits, for each, the JCS canonical text and its
// sha256 — so an external harness (tests/test_crosslang.py) can diff this independent Go implementation
// against infra/cwp/canonical.py byte-for-byte.
//
//	jcs-verify < corpus.json > results.json
//
// corpus.json: [{"name": "...", "input": <any JSON value>}, ...]
// results.json: [{"name": "...", "canonical": "...", "digest": "<sha256 hex>"}, ...]
package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
)

func convert(v interface{}) (interface{}, error) {
	switch t := v.(type) {
	case json.Number:
		return normalizeNumber(t.String())
	case map[string]interface{}:
		for k, e := range t {
			c, err := convert(e)
			if err != nil {
				return nil, err
			}
			t[k] = c
		}
		return t, nil
	case []interface{}:
		for i, e := range t {
			c, err := convert(e)
			if err != nil {
				return nil, err
			}
			t[i] = c
		}
		return t, nil
	default:
		return v, nil
	}
}

type vector struct {
	Name  string      `json:"name"`
	Input interface{} `json:"input"`
}

type result struct {
	Name      string `json:"name"`
	Canonical string `json:"canonical"`
	Digest    string `json:"digest"`
}

type sigVector struct {
	Name   string      `json:"name"`
	Pubkey string      `json:"pubkey"` // base64 of the raw 32-byte Ed25519 public key
	Env    sigEnvelope `json:"envelope"`
}

func runSig(verify func([]byte, sigEnvelope) bool) {
	var vecs []sigVector
	if err := json.NewDecoder(os.Stdin).Decode(&vecs); err != nil {
		fmt.Fprintln(os.Stderr, "decode sig corpus:", err)
		os.Exit(2)
	}
	type verdict struct {
		Name  string `json:"name"`
		Valid bool   `json:"valid"`
	}
	out := make([]verdict, 0, len(vecs))
	for _, v := range vecs {
		pub, err := base64.StdEncoding.DecodeString(v.Pubkey)
		if err != nil {
			fmt.Fprintf(os.Stderr, "sig vector %q: bad pubkey\n", v.Name)
			os.Exit(1)
		}
		out = append(out, verdict{v.Name, verify(pub, v.Env)})
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(out)
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "sig" { // pure Ed25519 (cwp native)
		runSig(verifyEnvelope)
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "phsig" { // Ed25519ph (cosign/sigstore DSSE — P0-T03 interop)
		runSig(verifyEnvelopePh)
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "chain" { // Ledger-v2 cold chain verify (P1-T04 anchor)
		runChain()
		return
	}
	dec := json.NewDecoder(os.Stdin)
	dec.UseNumber() // preserve number tokens so int/float is classified exactly as Python's json does
	var corpus []vector
	if err := dec.Decode(&corpus); err != nil {
		fmt.Fprintln(os.Stderr, "decode corpus:", err)
		os.Exit(2)
	}
	out := make([]result, 0, len(corpus))
	for _, v := range corpus {
		in, err := convert(v.Input)
		if err != nil {
			fmt.Fprintf(os.Stderr, "vector %q: %v\n", v.Name, err)
			os.Exit(1)
		}
		c, err := Canonicalize(in)
		if err != nil {
			fmt.Fprintf(os.Stderr, "vector %q: %v\n", v.Name, err)
			os.Exit(1)
		}
		d, _ := Digest(in)
		out = append(out, result{v.Name, c, d})
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, "encode results:", err)
		os.Exit(2)
	}
}

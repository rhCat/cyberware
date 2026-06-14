// Ledger-v2 cold chain verifier — the INDEPENDENT external anchor (meta-rule M3) for the cryptographic
// prev-hash chain (P1-T04). It reproduces infra/cwp/ledger.py verify_chain: recompute each record's prev
// as Digest(link_of(prior)) — Digest is the same RFC-8785 form as link_digest_v2 — and enforce the same
// structural rules (single origin-bound genesis, contiguous seq, one genesis). Any divergence from the
// Python verifier is a conformance bug in one of them; that is the point of a second implementation.
//
//	jcs-verify chain < chain-corpus.json > verdicts.json
//
// chain-corpus.json: [{"name","schema",2,"entries":[…],"expect_run_id"?,"expect_plan_sha"?}, …]
// verdicts.json:     [{"name","ok":bool,"problem":string}, …]
package main

import (
	"encoding/json"
	"fmt"
	"os"
)

const zeroDigest = "0000000000000000000000000000000000000000000000000000000000000000"

type chainVec struct {
	Name          string                   `json:"name"`
	Schema        int                      `json:"schema"`
	Entries       []map[string]interface{} `json:"entries"`
	ExpectRunID   *string                  `json:"expect_run_id"`
	ExpectPlanSha *string                  `json:"expect_plan_sha"`
}

type chainVerdict struct {
	Name    string `json:"name"`
	OK      bool   `json:"ok"`
	Problem string `json:"problem"`
}

// seqInt returns the integer value of a JSON seq, rejecting bool/float/string/absent (mirrors Python's
// _seq_int: a sequence number must be a real integer).
func seqInt(v interface{}) (int64, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	i, err := n.Int64() // errors on "1.5"/"1e2" — only a plain integer token passes
	if err != nil {
		return 0, false
	}
	return i, true
}

// linkDigest computes Digest(link_of(e)) — the entry minus its own back-pointer `prev`, RFC-8785-digested.
func linkDigest(e map[string]interface{}) (string, error) {
	link := make(map[string]interface{}, len(e))
	for k, v := range e {
		if k != "prev" {
			link[k] = v
		}
	}
	conv, err := convert(link)
	if err != nil {
		return "", err
	}
	return Digest(conv)
}

func nonEmptyStr(v interface{}) bool {
	s, ok := v.(string)
	return ok && s != ""
}

func verifyChain(v chainVec) (bool, string) {
	if v.Schema != 2 {
		return false, fmt.Sprintf("schema %d unsupported by the Go anchor (reproduces v2 only)", v.Schema)
	}
	if len(v.Entries) == 0 {
		return false, "empty chain — a provenance chain must contain at least the genesis"
	}
	g := v.Entries[0]
	if g["type"] != "genesis" {
		return false, fmt.Sprintf("entry[0] is not a genesis record (type=%v)", g["type"])
	}
	if g["prev"] != zeroDigest {
		return false, "entry[0] (genesis) prev is not the all-zero root"
	}
	bound := (nonEmptyStr(g["run_id"]) && nonEmptyStr(g["plan_sha"])) ||
		nonEmptyStr(g["supersedes_head"]) || nonEmptyStr(g["supersedes"])
	if !bound {
		return false, "entry[0] (genesis) binds no origin (need run_id+plan_sha, or supersedes for a migration)"
	}
	if v.ExpectRunID != nil && g["run_id"] != *v.ExpectRunID {
		return false, fmt.Sprintf("genesis run_id %v != expected %q (transplant)", g["run_id"], *v.ExpectRunID)
	}
	if v.ExpectPlanSha != nil && g["plan_sha"] != *v.ExpectPlanSha {
		return false, fmt.Sprintf("genesis plan_sha %v != expected %q (transplant)", g["plan_sha"], *v.ExpectPlanSha)
	}
	prevDigest := zeroDigest
	var lastSeq int64
	haveSeq := false
	for i, e := range v.Entries {
		who := fmt.Sprintf("entry[%d] (id=%v)", i, e["task_id"])
		if i > 0 && (e["type"] == "genesis" || e["prev"] == zeroDigest) {
			return false, who + ": a second genesis / all-zero-prev record mid-chain"
		}
		if e["prev"] != prevDigest {
			return false, who + ": prev != recomputed (tamper or transplant)"
		}
		seq, ok := seqInt(e["seq"])
		if i == 0 {
			haveSeq = ok // genesis seq optional; seeds contiguity only if present
			lastSeq = seq
		} else if !ok {
			return false, who + ": seq missing or not an integer (replay/insert guard)"
		} else if haveSeq && seq != lastSeq+1 {
			return false, fmt.Sprintf("%s: seq %d not contiguous after %d (insert/delete)", who, seq, lastSeq)
		} else {
			haveSeq = true
			lastSeq = seq
		}
		d, err := linkDigest(e)
		if err != nil {
			return false, fmt.Sprintf("%s: digest error: %v", who, err)
		}
		prevDigest = d
	}
	return true, ""
}

func runChain() {
	dec := json.NewDecoder(os.Stdin)
	dec.UseNumber() // exact int/float classification, matching Python's json + canonical.py
	var vecs []chainVec
	if err := dec.Decode(&vecs); err != nil {
		fmt.Fprintln(os.Stderr, "decode chain corpus:", err)
		os.Exit(2)
	}
	out := make([]chainVerdict, 0, len(vecs))
	for _, v := range vecs {
		ok, prob := verifyChain(v)
		out = append(out, chainVerdict{v.Name, ok, prob})
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(out)
}

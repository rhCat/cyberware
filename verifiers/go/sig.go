package main

// Independent Go verification of cyberware's DSSE / Ed25519 signatures (the sig-verdict half of the
// external anchor, P0-T08). Mirrors infra/cwp/sign.py: the signed message is the DSSE PAE of the
// payload; Ed25519 is deterministic, so a signature produced by sign.py verifies here unchanged.

import (
	"crypto/ed25519"
	"encoding/base64"
	"fmt"
)

// pae reproduces the DSSE Pre-Authentication Encoding from infra/cwp/sign.py byte-for-byte.
func pae(payloadType string, payload []byte) []byte {
	hdr := fmt.Sprintf("DSSEv1 %d %s %d ", len(payloadType), payloadType, len(payload))
	return append([]byte(hdr), payload...)
}

type sigEnvelope struct {
	Payload     string `json:"payload"`
	PayloadType string `json:"payloadType"`
	Signatures  []struct {
		Keyid string `json:"keyid"`
		Sig   string `json:"sig"`
	} `json:"signatures"`
}

// verifyEnvelope returns true iff some signature verifies against the raw public key over the PAE.
func verifyEnvelope(publicRaw []byte, env sigEnvelope) bool {
	payload, err := base64.StdEncoding.DecodeString(env.Payload)
	if err != nil || len(publicRaw) != ed25519.PublicKeySize {
		return false
	}
	msg := pae(env.PayloadType, payload)
	pub := ed25519.PublicKey(publicRaw)
	for _, s := range env.Signatures {
		sig, err := base64.StdEncoding.DecodeString(s.Sig)
		if err == nil && ed25519.Verify(pub, msg, sig) {
			return true
		}
	}
	return false
}

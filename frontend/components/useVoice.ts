"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

/** Speech to text with the browser's own speech recognition (Chrome, Edge, Safari). Nothing is recorded or stored by
 *  MoneyMap: the browser turns speech into text and the text goes into the box for you to check before sending. */
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
  start: () => void; stop: () => void;
};

function make(): Recognition | null {
  if (typeof window === "undefined") return null;
  const W = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  const Ctor = W.SpeechRecognition ?? W.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

const noop = () => () => {};
const hasSpeech = () => "SpeechRecognition" in window || "webkitSpeechRecognition" in window;

export function useVoice(onText: (text: string, final: boolean) => void) {
  const supported = useSyncExternalStore(noop, hasSpeech, () => false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const cb = useRef(onText);
  useEffect(() => { cb.current = onText; }, [onText]);

  const stop = useCallback(() => { rec.current?.stop(); }, []);
  const start = useCallback(() => {
    const r = make();
    if (!r) return;
    rec.current = r;
    r.lang = navigator.language || "en-GB";
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => {
      let text = "";
      let final = false;
      for (let i = 0; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
        final = e.results[i].isFinal;
      }
      cb.current(text, final);
    };
    r.onerror = (e) => setError(e.error === "not-allowed" ? "Allow the microphone for this site to talk to MoneyMap." : null);
    r.onend = () => setListening(false);
    setError(null);
    setListening(true);
    r.start();
  }, []);

  useEffect(() => () => rec.current?.stop(), []);
  return { supported, listening, error, start, stop };
}

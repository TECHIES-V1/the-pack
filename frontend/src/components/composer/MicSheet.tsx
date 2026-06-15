import { useEffect, useRef } from "react";

interface MicSheetProps {
  onTranscript: (text: string) => void;
}

export function MicSheet({ onTranscript }: MicSheetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    });
    ro.observe(canvas);
    canvas.width = canvas.offsetWidth || 560;
    canvas.height = canvas.offsetHeight || 20;

    // --- Waveform tuning ---
    // SPEED: increase to animate faster, decrease for slower pulse (default: 1.8)
    const SPEED = 1;
    // BAR_WIDTH: pixel width of each bar (default: 3)
    const BAR_WIDTH = 3;
    // GAP: pixel gap between bars (default: 2)
    const GAP = 2;
    // MAX_HEIGHT_RATIO: max bar height as fraction of canvas height (default: 0.85)
    const MAX_HEIGHT_RATIO = 0.85;
    // MIN_HEIGHT: minimum bar height in px (default: 3)
    const MIN_HEIGHT = 3;
    // --- end tuning ---

    let t = 0;
    function draw() {
      if (!canvas || !ctx) return;
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      const barCount = Math.floor(W / (BAR_WIDTH + GAP));
      const maxH = H * MAX_HEIGHT_RATIO;
      for (let i = 0; i < barCount; i++) {
        const x = i * (BAR_WIDTH + GAP);
        const norm = i / barCount;
        // bell curve envelope — tall in the middle, short at edges
        const envelope = Math.pow(Math.sin(norm * Math.PI), 0.6);
        // layered sin waves for organic variation
        const wave =
          0.5 * Math.abs(Math.sin(t * SPEED + i * 0.35)) +
          0.3 * Math.abs(Math.sin(t * SPEED * 1.3 + i * 0.6 + 1.2)) +
          0.2 * Math.abs(Math.sin(t * SPEED * 0.7 + i * 0.9 + 2.5));
        const height = MIN_HEIGHT + envelope * maxH * wave;
        const y = (H - height) / 2;
        // left ~45% dim, right ~55% bright white — matches ChatGPT style
        ctx.fillStyle = norm < 0.45 ? "#4a4a4a" : "#ffffff";
        ctx.beginPath();
        ctx.roundRect(x, y, BAR_WIDTH, height, BAR_WIDTH / 2);
        ctx.fill();
      }
      t += 0.04;
      animRef.current = requestAnimationFrame(draw);
    }
    draw();

    const SpeechRecognitionAPI =
      (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
    if (SpeechRecognitionAPI) {
      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognitionRef.current = recognition;
      let finalText = "";
      recognition.onresult = (e: any) => {
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) finalText += e.results[i][0].transcript + " ";
          else onTranscript((finalText + e.results[i][0].transcript).trim());
        }
        if (finalText) onTranscript(finalText.trim());
      };
      recognition.start();
    }

    return () => {
      ro.disconnect();
      cancelAnimationFrame(animRef.current);
      recognitionRef.current?.stop();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      height={36}
      className="flex-1 h-9 w-full block"
    />
  );
}

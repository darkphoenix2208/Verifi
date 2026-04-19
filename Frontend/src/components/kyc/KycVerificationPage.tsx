import { useEffect, useMemo, useRef, useState } from "react";

interface KycVerifyResponse {
  success: boolean;
  confidence: number;
  liveness_passed: boolean;
  id_match_passed: boolean;
  details: Record<string, unknown>;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function KycVerificationPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [capturedPreviewUrl, setCapturedPreviewUrl] = useState<string>("");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<KycVerifyResponse | null>(null);

  useEffect(() => {
    const setupCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720 },
          audio: false
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
      } catch (cameraError) {
        setError(
          cameraError instanceof Error
            ? `Camera error: ${cameraError.message}`
            : "Unable to access webcam."
        );
      }
    };

    setupCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (capturedPreviewUrl) {
        URL.revokeObjectURL(capturedPreviewUrl);
      }
    };
  }, [capturedPreviewUrl]);

  const canVerify = useMemo(() => Boolean(capturedBlob && idFile && !isVerifying), [capturedBlob, idFile, isVerifying]);

  const handleCapturePhoto = async () => {
    setError("");
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      setError("Camera is not ready yet.");
      return;
    }

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) {
      setError("Failed to initialize capture context.");
      return;
    }

    context.drawImage(video, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((value) => resolve(value), "image/jpeg", 0.92);
    });

    if (!blob) {
      setError("Could not capture image from webcam.");
      return;
    }

    if (capturedPreviewUrl) {
      URL.revokeObjectURL(capturedPreviewUrl);
    }

    const previewUrl = URL.createObjectURL(blob);
    setCapturedBlob(blob);
    setCapturedPreviewUrl(previewUrl);
  };

  const handleVerifyIdentity = async () => {
    if (!capturedBlob || !idFile) {
      setError("Please capture a selfie and upload an ID card image before verification.");
      return;
    }

    setIsVerifying(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", new File([capturedBlob], "webcam_capture.jpg", { type: "image/jpeg" }));
      formData.append("id_card", idFile);

      const response = await fetch(`${API_BASE_URL}/api/kyc/verify`, {
        method: "POST",
        body: formData
      });

      const body = (await response.json()) as KycVerifyResponse | { detail?: string };
      if (!response.ok) {
        const message = "detail" in body && body.detail ? body.detail : `KYC verify failed with ${response.status}`;
        throw new Error(message);
      }
      setResult(body as KycVerifyResponse);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "KYC verification failed.");
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-7xl space-y-6">
      <header className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="text-2xl font-semibold text-zinc-100">KYC Verification</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Capture live selfie and upload ID document to validate identity and liveness.
        </p>
      </header>

      {error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <h3 className="mb-3 text-lg font-semibold text-zinc-100">Live Webcam</h3>
          <div className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-950">
            <video ref={videoRef} className="h-[320px] w-full object-cover" muted playsInline />
          </div>
          <button
            type="button"
            onClick={handleCapturePhoto}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
          >
            Capture Photo
          </button>
          {capturedPreviewUrl ? (
            <div className="mt-4">
              <p className="mb-2 text-xs uppercase tracking-wide text-zinc-400">Captured Preview</p>
              <img
                src={capturedPreviewUrl}
                alt="Captured webcam frame"
                className="h-44 w-full rounded-xl border border-zinc-700 object-cover"
              />
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <h3 className="mb-3 text-lg font-semibold text-zinc-100">Identity Document</h3>
          <label className="mb-2 block text-sm text-zinc-300" htmlFor="id-upload">
            Upload ID card image
          </label>
          <input
            id="id-upload"
            type="file"
            accept="image/*"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setIdFile(file);
            }}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 file:mr-3 file:rounded-md file:border-0 file:bg-zinc-800 file:px-3 file:py-1.5 file:text-zinc-100"
          />

          <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-sm text-zinc-300">
            <p>
              <span className="text-zinc-400">Selfie:</span>{" "}
              {capturedBlob ? "Captured" : "Not captured"}
            </p>
            <p className="mt-1">
              <span className="text-zinc-400">ID Image:</span>{" "}
              {idFile ? idFile.name : "Not selected"}
            </p>
          </div>

          <button
            type="button"
            onClick={handleVerifyIdentity}
            disabled={!canVerify}
            className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isVerifying ? "Verifying..." : "Verify Identity"}
          </button>

          {result ? (
            <div className="mt-5 rounded-xl border border-zinc-700 bg-zinc-950 p-4">
              <p className="text-sm font-semibold text-zinc-100">Verification Result</p>
              <div className="mt-3 space-y-2 text-sm">
                <p className="text-zinc-300">
                  Liveness Check:{" "}
                  <span className={result.liveness_passed ? "text-emerald-300" : "text-red-300"}>
                    {result.liveness_passed ? "PASSED" : "FAILED"}
                  </span>
                </p>
                <p className="text-zinc-300">
                  ID Match:{" "}
                  <span className={result.id_match_passed ? "text-emerald-300" : "text-red-300"}>
                    {result.id_match_passed ? "PASSED" : "FAILED"}
                  </span>
                </p>
                <p className="text-zinc-300">
                  Confidence: <span className="text-zinc-100">{formatPercent(result.confidence)}</span>
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </section>
  );
}

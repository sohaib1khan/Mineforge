import Hls from "hls.js";
import { useEffect, useRef, useState } from "react";

import { Button } from "../../components/ui/Button";
import { streamHlsPlaylistUrl } from "../../lib/api";

type Props = {
  live: boolean;
  hlsPath?: string | null;
};

export function StreamPlayer({ live, hlsPath }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [muted, setMuted] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pipSupported, setPipSupported] = useState(false);

  useEffect(() => {
    setPipSupported(
      typeof document !== "undefined" && Boolean(document.pictureInPictureEnabled),
    );
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !live) {
      hlsRef.current?.destroy();
      hlsRef.current = null;
      if (video) {
        video.removeAttribute("src");
        video.load();
      }
      return;
    }

    const src = streamHlsPlaylistUrl(hlsPath);
    setError(null);

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
      void video.play().catch(() => {
        /* autoplay may be blocked until unmute */
      });
      return () => {
        video.removeAttribute("src");
        video.load();
      };
    }

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: false,
        backBufferLength: 30,
        xhrSetup: (xhr) => {
          xhr.withCredentials = true;
        },
      });
      hlsRef.current = hls;
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        void video.play().catch(() => undefined);
      });
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
          hls.startLoad();
          return;
        }
        if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          hls.recoverMediaError();
          return;
        }
        setError("Playback failed — retrying…");
        hls.destroy();
        hlsRef.current = null;
      });
      return () => {
        hls.destroy();
        hlsRef.current = null;
      };
    }

    setError("HLS is not supported in this browser.");
    return undefined;
  }, [live, hlsPath]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.muted = muted;
  }, [muted]);

  const toggleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.fullscreenElement) {
      void document.exitFullscreen();
      return;
    }
    void video.requestFullscreen?.();
  };

  const togglePiP = () => {
    const video = videoRef.current;
    if (!video || !document.pictureInPictureEnabled) return;
    if (document.pictureInPictureElement) {
      void document.exitPictureInPicture();
      return;
    }
    void video.requestPictureInPicture();
  };

  return (
    <div className="space-y-3">
      <div className="relative aspect-video overflow-hidden rounded-md border border-border bg-bg">
        {live ? (
          <video
            ref={videoRef}
            className="h-full w-full object-contain"
            playsInline
            controls={false}
            muted={muted}
            autoPlay
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <p className="font-pixel text-lg text-muted">Not live right now</p>
            <p className="max-w-sm text-sm text-muted">
              When the admin starts OBS, this player will connect automatically.
            </p>
          </div>
        )}
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {live ? (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setMuted((m) => !m)}>
            {muted ? "Unmute" : "Mute"}
          </Button>
          <Button variant="secondary" onClick={toggleFullscreen}>
            Fullscreen
          </Button>
          {pipSupported ? (
            <Button variant="secondary" onClick={togglePiP}>
              Picture in picture
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

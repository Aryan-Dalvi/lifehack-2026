import { ImageOff } from "lucide-react";
import { useEffect, useState } from "react";
import { apiObjectUrl } from "../../api";

/**
 * A thumbnail from a catalog that has not been published yet.
 *
 * Those bytes are merchant-only, and an <img src> cannot carry the merchant key, so the
 * picture is fetched with credentials and shown from an object URL that is revoked when the
 * row leaves the table. A workbook image_url is an ordinary public link and renders directly.
 */
export function StagedImage({ src, alt }: { src: string | null; alt: string }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const needsCredentials = Boolean(src && src.includes("/catalog/images/"));

  useEffect(() => {
    if (!src || !needsCredentials) return;
    let revoked = false;
    let created: string | null = null;
    apiObjectUrl(src.replace(/^\/api/, ""))
      .then((url) => {
        if (revoked) {
          if (url) URL.revokeObjectURL(url);
          return;
        }
        created = url;
        setObjectUrl(url);
        setFailed(url === null);
      })
      .catch(() => setFailed(true));
    return () => {
      revoked = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [src, needsCredentials]);

  const resolved = needsCredentials ? objectUrl : src;
  if (!src || failed || (needsCredentials && !objectUrl)) {
    return (
      <span className="staged-image staged-image--empty" title={src ? "Preview unavailable" : "No image"}>
        <ImageOff size={13} />
      </span>
    );
  }
  return <img className="staged-image" src={resolved ?? ""} alt={alt} loading="lazy" onError={() => setFailed(true)} />;
}

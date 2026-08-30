type VisaBrandMarkProps = {
  className?: string;
};

/**
 * Visa's official blue Brand Mark, served locally so the demo never depends on venue Wi-Fi.
 * Source: https://cdn.visa.com/v2/assets/images/logos/visa/blue/logo.png
 */
export function VisaBrandMark({ className = "" }: VisaBrandMarkProps) {
  return (
    <img
      className={`visa-brand-mark ${className}`.trim()}
      src="/visa-brand-mark.png"
      alt="Visa"
      width="208"
      height="68"
      draggable="false"
    />
  );
}

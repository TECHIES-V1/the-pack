// Alpha's face for chat — the same amber star he wears on the canvas (ROLE_COLOR.alpha), so the
// conversation feels like it's coming from the leader of the Pack, not a faceless box.
// Color is hardcoded (not imported from the canvas) to keep React Flow out of the Door bundle.

import { FaStar } from "react-icons/fa";

export function AlphaAvatar({ size = 26 }: { size?: number }) {
  return (
    <span
      className="shrink-0 inline-flex items-center justify-center rounded-full text-white"
      style={{ width: size, height: size, background: "#e6a23c", fontSize: size * 0.48 }}
    >
      <FaStar />
    </span>
  );
}

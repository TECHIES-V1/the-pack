import { motion } from "framer-motion";

interface InstinctChipProps {
  title: string;
  subtitle: string;
  onClick?: () => void;
  disabled?: boolean;
}

export function InstinctChip({ title, subtitle, onClick, disabled }: InstinctChipProps) {
  return (
    <motion.button
      onClick={disabled ? undefined : onClick}
      whileHover={disabled ? {} : { borderColor: "#555" }}
      whileTap={disabled ? {} : { scale: 0.98 }}
      transition={{ duration: 0.15 }}
      className={`w-[168px] shrink-0 bg-transparent border border-door-border rounded-xl px-4 py-3.5 text-left font-sans transition-opacity duration-200 ${
        disabled ? "opacity-30 cursor-default" : "text-white cursor-pointer"
      }`}
    >
      <div className="text-[15px] font-medium mb-1">{title}</div>
      <div className="text-[13px] text-door-dim">{subtitle}</div>
    </motion.button>
  );
}

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FaStar } from "react-icons/fa";
import {
  LuChartBar,
  LuRoute,
  LuTarget,
  LuPen,
  LuPanelRight,
} from "react-icons/lu";
import { BiSolidBarChartAlt2 } from "react-icons/bi";
import { PiCrosshairBold } from "react-icons/pi";
import type { PlanView } from "@/events/reducer";

const WOLVES = [
  {
    role: "Alpha",
    desc: "Reading your task, building the plan, keeping the pack on track",
    icon: <FaStar size={16} />,
  },
  {
    role: "Beta",
    desc: "Breaking your goal into steps before the hunt begins",
    icon: <BiSolidBarChartAlt2 size={16} />,
  },
  {
    role: "Scout",
    desc: "Ranging ahead to find ground truth — three running at once",
    icon: <LuRoute size={16} />,
  },
  {
    role: "Tracker",
    desc: "Reading what the Scouts bring back and giving it shape",
    icon: <PiCrosshairBold size={16} />,
  },
  {
    role: "Howler",
    desc: "Writing the final brief and signaling the pack is done",
    icon: <LuPen size={16} />,
  },
];

interface Props {
  plan: PlanView;
  onApprove: () => void;
  onBack: () => void;
}

export function PlanSidebar({
  onApprove: _approve,
  onBack: _back,
  plan: _plan,
}: Props) {
  const [open, setOpen] = useState(true);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="shrink-0 flex items-start pt-6 px-8 bg-[#1A1A1A] text-[#a1a1aa] hover:text-white transition-colors cursor-pointer m-2 rounded-[12px] border border-[#2a2a2a] overflow-hidden"
      >
        <LuPanelRight size={20} />
      </button>
    );
  }

  return (
    <aside className="w-[300px] shrink-0 flex flex-col bg-[#1A1A1A] text-white overflow-hidden m-2 rounded-[12px] border border-[#2a2a2a]">
      {/* Header */}
      <div className="px-5 pt-6 pb-6 border-b border-[#2a2a2a] flex justify-between items-start">
        <div className="flex flex-col gap-3">
          <h2 className="text-[16px] font-medium tracking-wide m-0 leading-none">
            The Pack
          </h2>
          <span className="bg-[#404040] text-[#a1a1aa] text-[11px] font-medium px-3 py-1.5 rounded-full w-fit leading-none">
            Ready to hunt
          </span>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-[#a1a1aa] hover:text-white transition-colors bg-transparent border-none cursor-pointer p-0 mt-1"
        >
          <LuPanelRight size={20} />
        </button>
      </div>

      {/* Wolves List */}
      <div className="flex-1 overflow-y-auto px-5 py-6 flex flex-col gap-8 scrollbar-subtle pr-3">
        {WOLVES.map((wolf) => (
          <div key={wolf.role} className="flex flex-col gap-3">
            <div className="relative w-14 h-14 flex items-center justify-center shrink-0 -ml-1">
              <div className="absolute inset-0 rounded-full border border-white/[0.02]" />
              <div className="absolute inset-1.5 rounded-full border border-[#404040]" />
              <div className="relative w-9 h-9 rounded-full bg-[#1A1A1A] border border-[#727272] flex items-center justify-center text-[#404040] z-10">
                {wolf.icon}
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <h3 className="text-[14px] font-medium m-0 leading-none text-white">
                {wolf.role}
              </h3>
              <p className="text-[13px] text-[#a1a1aa] m-0 leading-snug">
                {wolf.desc}
              </p>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

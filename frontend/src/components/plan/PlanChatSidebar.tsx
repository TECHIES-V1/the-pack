import { useState } from "react";
import { OneBox } from "@/components/composer/OneBox";

export function PlanChatSidebar() {
  const [messages, setMessages] = useState<string[]>([]);

  return (
    <aside className="w-[340px] shrink-0 flex flex-col bg-[#1A1A1A] text-white overflow-hidden m-2 rounded-[12px] border border-[#2a2a2a]">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-[#2a2a2a]">
        <h2 className="text-[14px] font-medium m-0 leading-none">Chat session</h2>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 scrollbar-subtle">
        {messages.map((msg, i) => (
          <div key={i} className="bg-[#242424] rounded-xl p-4 text-[13px] leading-relaxed text-[#d4d4d8] self-end max-w-[90%]">
            {msg}
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-4 pt-2">
        <OneBox 
          placeholder="Ask Alpha anything about this plan..." 
          onSubmit={(payload) => setMessages((prev) => [...prev, payload.text])}
        />
      </div>
    </aside>
  );
}

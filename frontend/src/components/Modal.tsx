import React, { useEffect } from "react";
import { X } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl";
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = "lg",
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthClass = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
    xl: "max-w-xl",
    "2xl": "max-w-2xl",
  }[maxWidth];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-150">
      <div
        className={`w-full ${maxWidthClass} bg-slate-900/95 backdrop-blur-xl border border-white/[0.09] rounded-2xl shadow-2xl shadow-black/80 flex flex-col max-h-[90vh] overflow-hidden relative card-specular ring-1 ring-white/5 animate-in zoom-in-95 duration-150`}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.07] bg-slate-950/30">
          <h3 className="font-bold text-slate-100 text-sm tracking-tight">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="btn-press text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-white/[0.08] transition-colors"
          >
            <X size={16} />
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1 text-slate-300 text-sm">{children}</div>
      </div>
    </div>
  );
};

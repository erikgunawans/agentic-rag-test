import React, { useState } from "react";
import {
  Folder,
  Home,
  FilePlus,
  GitCompare,
  ShieldCheck,
  Scale,
  MessageSquare,
  ChevronLeft,
  Plus,
  Search,
  Settings,
  FileText,
  Mic,
  Send,
  Sparkles,
  Layers,
  Square,
  Award,
  Target,
  Map,
  Columns,
  Clock,
  LayoutGrid,
} from "lucide-react";
import { Documents } from "./components/Documents";
import { DocumentCreation } from "./components/DocumentCreation";
import { DocumentComparison } from "./components/DocumentComparison";
import { ComplianceCheck } from "./components/ComplianceCheck";
import { ContractAnalysis } from "./components/ContractAnalysis";
import { FormVariantsReference } from "./components/FormVariantsReference";
import { TextInputStates } from "./components/TextInputStates";
import { ComplianceStatusReference } from "./components/ComplianceStatusReference";
import { AnalysisControlsReference } from "./components/AnalysisControlsReference";
import { KnowledgeHubOverview } from "./components/KnowledgeHubOverview";
import { IconRailReference } from "./components/IconRailReference";
import { ColumnHeaderReference } from "./components/ColumnHeaderReference";
import { HistorySectionReference } from "./components/HistorySectionReference";
import { IconRailGroupReference } from "./components/IconRailGroupReference";
import { ColumnHeader } from "./components/shared";

export default function App() {
  const [activeNav, setActiveNav] = useState(10); // Show Knowledge Hub Overview by default
  const [selectedChat, setSelectedChat] = useState<
    number | null
  >(null);
  const [hoveredCard, setHoveredCard] = useState<number | null>(
    null,
  );
  const [isFocused, setIsFocused] = useState(true); // Show focused state by default
  const [showAllCardHovers, setShowAllCardHovers] =
    useState(true); // Show all card hover states

  const navIcons = [
    { Icon: Folder, id: 0 },
    { Icon: Home, id: 1 },
    { Icon: FilePlus, id: 2 },
    { Icon: GitCompare, id: 3 },
    { Icon: ShieldCheck, id: 4 },
    { Icon: Scale, id: 5 },
    { Icon: Layers, id: 6 }, // Form Variants Reference
    { Icon: Square, id: 7 }, // Text Input States
    { Icon: Award, id: 8 }, // Compliance Status Reference
    { Icon: Target, id: 9 }, // Analysis Controls Reference
    { Icon: Map, id: 10 }, // Knowledge Hub Overview
    { Icon: Columns, id: 11 }, // Icon Rail Reference
    { Icon: Clock, id: 12 }, // History Section Reference
    { Icon: LayoutGrid, id: 13 }, // Icon Rail Group Reference
  ];

  const conversations = [
    {
      id: 1,
      title: "NDA compliance check",
      time: "5h ago",
      group: "TODAY",
    },
    {
      id: 2,
      title: "Contract expiration dates",
      time: "2h ago",
      group: "TODAY",
    },
    {
      id: 3,
      title: "Risk analysis PT Marina",
      time: "1d ago",
      group: "YESTERDAY",
    },
    {
      id: 4,
      title: "Payment terms summary",
      time: "2d ago",
      group: "LAST WEEK",
    },
    {
      id: 5,
      title: "Termination clauses",
      time: "3d ago",
      group: "LAST WEEK",
    },
    {
      id: 6,
      title: "License agreement review",
      time: "4d ago",
      group: "LAST WEEK",
    },
    {
      id: 7,
      title: "Compliance status check",
      time: "5d ago",
      group: "LAST WEEK",
    },
  ];

  const quickActions = [
    {
      id: 1,
      title: "Pembuatan Dokumen",
      subtitle: "Draft NDAs, kontrak & perjanjian",
      Icon: FilePlus,
      color: "#7C5CFC",
      glowColor: "rgba(124, 92, 252, 0.15)",
      borderColor: "rgba(124, 92, 252, 0.4)",
    },
    {
      id: 2,
      title: "Perbandingan Dokumen",
      subtitle: "Bandingkan versi & temukan perbedaan",
      Icon: GitCompare,
      color: "#22D3EE",
      glowColor: "rgba(34, 211, 238, 0.15)",
      borderColor: "rgba(34, 211, 238, 0.4)",
    },
    {
      id: 3,
      title: "Kepatuhan Dokumen",
      subtitle: "Cek regulasi & persyaratan hukum",
      Icon: ShieldCheck,
      color: "#34D399",
      glowColor: "rgba(52, 211, 153, 0.15)",
      borderColor: "rgba(52, 211, 153, 0.4)",
    },
    {
      id: 4,
      title: "Analisis Kontrak",
      subtitle: "Identifikasi risiko & klausul kritis",
      Icon: Scale,
      color: "#F59E0B",
      glowColor: "rgba(245, 158, 11, 0.15)",
      borderColor: "rgba(245, 158, 11, 0.4)",
    },
  ];

  const groupedConversations = conversations.reduce(
    (acc, conv) => {
      if (!acc[conv.group]) acc[conv.group] = [];
      acc[conv.group].push(conv);
      return acc;
    },
    {} as Record<string, typeof conversations>,
  );

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      {/* Column 1 - Icon Rail (always visible, but simpler when documents active) */}
      <div
        className="relative flex items-center justify-center"
        style={{
          width: activeNav === 0 ? "60px" : "88px",
          backgroundColor:
            activeNav === 0 ? "#080C14" : "#0B1120",
          transition: "width 0.2s",
        }}
      >
        {activeNav === 0 ? (
          // Simpler icon rail for documents view
          <div className="flex flex-col items-center gap-2 py-4">
            {/* Logo */}
            <div
              className="flex items-center justify-center rounded-lg transition-all duration-200 mb-2"
              style={{
                width: "40px",
                height: "40px",
                backgroundColor: "#7C5CFC",
                boxShadow: "0 0 16px rgba(124, 92, 252, 0.5)",
              }}
            >
              <Sparkles size={24} color="white" />
            </div>

            {/* Divider */}
            <div
              className="mb-1"
              style={{
                width: "24px",
                height: "1px",
                backgroundColor: "#1E2D45",
              }}
            />

            {/* Navigation Icons */}
            {navIcons.map(({ Icon, id }) => (
              <button
                key={id}
                onClick={() => setActiveNav(id)}
                className="flex items-center justify-center rounded-lg transition-all duration-200"
                style={{
                  width: "36px",
                  height: "36px",
                  backgroundColor:
                    activeNav === id
                      ? "rgba(124, 92, 252, 0.12)"
                      : "transparent",
                  color:
                    activeNav === id ? "#7C5CFC" : "#94A3B8",
                  boxShadow:
                    activeNav === id
                      ? "0 0 16px rgba(124, 92, 252, 0.3)"
                      : "none",
                }}
                onMouseEnter={(e) => {
                  if (activeNav !== id) {
                    e.currentTarget.style.backgroundColor =
                      "#1C2840";
                    e.currentTarget.style.color = "#F1F5F9";
                  }
                }}
                onMouseLeave={(e) => {
                  if (activeNav !== id) {
                    e.currentTarget.style.backgroundColor =
                      "transparent";
                    e.currentTarget.style.color = "#94A3B8";
                  }
                }}
              >
                <Icon size={20} />
              </button>
            ))}

            {/* Spacer */}
            <div className="flex-grow min-h-[20px]" />

            {/* Avatar */}
            <div className="relative">
              <div
                className="flex items-center justify-center rounded-full"
                style={{
                  width: "36px",
                  height: "36px",
                  backgroundColor: "#7C5CFC",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "white",
                }}
              >
                AS
              </div>
              {/* Presence dot */}
              <div
                className="absolute bottom-0 right-0 rounded-full"
                style={{
                  width: "10px",
                  height: "10px",
                  backgroundColor: "#22C55E",
                  border: "2px solid #080C14",
                }}
              />
            </div>
          </div>
        ) : (
          // Floating pill for non-documents view
          <div
            className="flex flex-col items-center gap-1.5 py-3 rounded-[28px]"
            style={{
              width: "56px",
              backgroundColor: "rgba(15, 24, 41, 0.7)",
              backdropFilter: "blur(24px)",
              border: "1px solid #1E2D45",
              boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
            }}
          >
            {/* Logo */}
            <div
              className="flex items-center justify-center rounded-lg transition-all duration-200"
              style={{
                width: "40px",
                height: "40px",
                backgroundColor: "#7C5CFC",
                boxShadow: "0 0 16px rgba(124, 92, 252, 0.5)",
              }}
            >
              <Sparkles size={28} color="white" />
            </div>

            {/* Divider */}
            <div
              className="my-1"
              style={{
                width: "24px",
                height: "1px",
                backgroundColor: "#1E2D45",
              }}
            />

            {/* Navigation Icons */}
            {navIcons.map(({ Icon, id }) => (
              <button
                key={id}
                onClick={() => setActiveNav(id)}
                className="flex items-center justify-center rounded-lg transition-all duration-200"
                style={{
                  width: "36px",
                  height: "36px",
                  backgroundColor:
                    activeNav === id
                      ? "rgba(124, 92, 252, 0.12)"
                      : "transparent",
                  color:
                    activeNav === id ? "#7C5CFC" : "#94A3B8",
                  boxShadow:
                    activeNav === id
                      ? "0 0 16px rgba(124, 92, 252, 0.3)"
                      : "none",
                }}
                onMouseEnter={(e) => {
                  if (activeNav !== id) {
                    e.currentTarget.style.backgroundColor =
                      "#1C2840";
                    e.currentTarget.style.color = "#F1F5F9";
                  }
                }}
                onMouseLeave={(e) => {
                  if (activeNav !== id) {
                    e.currentTarget.style.backgroundColor =
                      "transparent";
                    e.currentTarget.style.color = "#94A3B8";
                  }
                }}
              >
                <Icon size={20} />
              </button>
            ))}

            {/* Spacer */}
            <div className="flex-grow min-h-[20px]" />

            {/* Avatar */}
            <div className="relative">
              <div
                className="flex items-center justify-center rounded-full"
                style={{
                  width: "36px",
                  height: "36px",
                  backgroundColor: "#7C5CFC",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "white",
                }}
              >
                AS
              </div>
              {/* Presence dot */}
              <div
                className="absolute bottom-0 right-0 rounded-full"
                style={{
                  width: "10px",
                  height: "10px",
                  backgroundColor: "#22C55E",
                  border: "2px solid #080C14",
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Conditional rendering: Documents view OR Chat sidebar + Welcome */}
      {activeNav === 0 ? (
        // Documents view - no chat sidebar
        <Documents />
      ) : activeNav === 2 ? (
        // Document Creation view
        <DocumentCreation />
      ) : activeNav === 3 ? (
        // Document Comparison view
        <DocumentComparison />
      ) : activeNav === 4 ? (
        // Compliance Check view
        <ComplianceCheck />
      ) : activeNav === 5 ? (
        // Contract Analysis view
        <ContractAnalysis />
      ) : activeNav === 6 ? (
        // Form Variants Reference view
        <FormVariantsReference />
      ) : activeNav === 7 ? (
        // Text Input States view
        <TextInputStates />
      ) : activeNav === 8 ? (
        // Compliance Status Reference view
        <ComplianceStatusReference />
      ) : activeNav === 9 ? (
        // Analysis Controls Reference view
        <AnalysisControlsReference />
      ) : activeNav === 10 ? (
        // Knowledge Hub Overview view
        <KnowledgeHubOverview />
      ) : activeNav === 11 ? (
        // Icon Rail Reference view
        <IconRailReference />
      ) : activeNav === 12 ? (
        // History Section Reference view
        <HistorySectionReference />
      ) : activeNav === 13 ? (
        // Icon Rail Group Reference view
        <IconRailGroupReference />
      ) : (
        <>
          {/* Column 2 - Chat History Sidebar */}
          <div
            className="flex flex-col"
            style={{
              width: "260px",
              backgroundColor: "#0F1829",
              borderRight: "1px solid #1E2D45",
            }}
          >
            {/* Header */}
            <ColumnHeader
              title="Knowledge Hub"
              subtitle="Chat History"
              rightIcon="chevron-left"
            />

            {/* New Chat Button */}
            <div className="px-4 pt-3 pb-2">
              <button
                className="w-full flex items-center justify-center gap-2 rounded-xl transition-all duration-200"
                style={{
                  height: "44px",
                  backgroundColor: "#7C5CFC",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "white",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor =
                    "#8B6EFD";
                  e.currentTarget.style.boxShadow =
                    "0 4px 20px rgba(124, 92, 252, 0.4)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor =
                    "#7C5CFC";
                  e.currentTarget.style.boxShadow = "none";
                }}
              >
                <Plus size={16} />
                New Chat
              </button>
            </div>

            {/* Search Bar */}
            <div className="px-3 py-2">
              <div
                className="flex items-center gap-2 px-3 rounded-[10px]"
                style={{
                  height: "36px",
                  backgroundColor: "#162033",
                  border: "1px solid #1E2D45",
                }}
              >
                <Search
                  size={16}
                  style={{ color: "#475569" }}
                />
                <input
                  type="text"
                  placeholder="Search conversations..."
                  className="flex-1 bg-transparent border-none outline-none"
                  style={{
                    fontSize: "13px",
                    color: "#F1F5F9",
                  }}
                />
              </div>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto relative">
              {Object.entries(groupedConversations).map(
                ([group, chats]) => (
                  <div key={group}>
                    <div
                      className="px-4 py-2"
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        color: "#475569",
                        letterSpacing: "0.08em",
                      }}
                    >
                      {group}
                    </div>
                    {chats.map((chat) => (
                      <button
                        key={chat.id}
                        onClick={() => setSelectedChat(chat.id)}
                        className="w-full flex items-center gap-2.5 px-4 transition-colors duration-150"
                        style={{
                          height: "52px",
                          backgroundColor:
                            selectedChat === chat.id
                              ? "#1C2840"
                              : "transparent",
                        }}
                        onMouseEnter={(e) => {
                          if (selectedChat !== chat.id) {
                            e.currentTarget.style.backgroundColor =
                              "#1C2840";
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (selectedChat !== chat.id) {
                            e.currentTarget.style.backgroundColor =
                              "transparent";
                          }
                        }}
                      >
                        <MessageSquare
                          size={16}
                          style={{
                            color: "#94A3B8",
                            flexShrink: 0,
                          }}
                        />
                        <div className="flex-1 flex flex-col gap-0.5 items-start min-w-0">
                          <div
                            className="truncate max-w-[140px]"
                            style={{
                              fontSize: "13px",
                              fontWeight: 500,
                              color: "#F1F5F9",
                            }}
                          >
                            {chat.title}
                          </div>
                        </div>
                        <div
                          style={{
                            fontSize: "11px",
                            color: "#475569",
                            flexShrink: 0,
                          }}
                        >
                          {chat.time}
                        </div>
                      </button>
                    ))}
                  </div>
                ),
              )}

              {/* Bottom fade overlay */}
              <div
                className="absolute bottom-0 left-0 right-0 pointer-events-none"
                style={{
                  height: "40px",
                  background:
                    "linear-gradient(to top, #0F1829, transparent)",
                }}
              />
            </div>

            {/* User Profile */}
            <div
              className="flex items-center gap-3 px-4"
              style={{
                height: "72px",
                borderTop: "1px solid #1E2D45",
              }}
            >
              <div
                className="flex items-center justify-center rounded-full"
                style={{
                  width: "36px",
                  height: "36px",
                  backgroundColor: "#334155",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "#F1F5F9",
                }}
              >
                EG
              </div>
              <div className="flex-1 flex flex-col gap-0.5">
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#F1F5F9",
                  }}
                >
                  Erik Gunawan
                </div>
                <div
                  style={{ fontSize: "11px", color: "#94A3B8" }}
                >
                  Konsultan Hukum
                </div>
              </div>
              <button
                className="transition-colors duration-200"
                style={{ color: "#94A3B8" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "#F1F5F9")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "#94A3B8")
                }
              >
                <Settings size={20} />
              </button>
            </div>
          </div>

          {/* Column 3 - Main Content Area */}
          <div
            className="flex-1 flex items-center justify-center relative overflow-hidden"
            style={{ backgroundColor: "#0B1120" }}
          >
            {/* Mesh Gradients */}
            <div
              className="absolute top-0 right-0 pointer-events-none"
              style={{
                width: "600px",
                height: "600px",
                background:
                  "radial-gradient(circle, rgba(76, 29, 149, 0.06) 0%, transparent 70%)",
              }}
            />
            <div
              className="absolute bottom-0 left-0 pointer-events-none"
              style={{
                width: "500px",
                height: "500px",
                background:
                  "radial-gradient(circle, rgba(10, 31, 61, 0.3) 0%, transparent 70%)",
              }}
            />

            {/* Content */}
            <div className="relative z-10 flex flex-col items-center">
              {/* Hero Group */}
              <div className="flex flex-col items-center gap-3 mb-8">
                {/* Logo + Greeting */}
                <div className="flex items-center gap-3.5">
                  <Sparkles size={44} color="white" />
                  <h1
                    style={{
                      fontSize: "38px",
                      fontWeight: 700,
                      lineHeight: 1.1,
                      letterSpacing: "-0.02em",
                    }}
                  >
                    <span style={{ color: "#F1F5F9" }}>
                      Hi,{" "}
                    </span>
                    <span
                      style={{
                        background:
                          "linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent",
                        backgroundClip: "text",
                      }}
                    >
                      Erik Gunawan
                    </span>
                  </h1>
                </div>

                {/* Subtitle */}
                <p
                  className="text-center"
                  style={{
                    fontSize: "16px",
                    color: "#94A3B8",
                    lineHeight: 1.6,
                    maxWidth: "560px",
                  }}
                >
                  Ask questions about your legal documents,
                  contracts, and compliance requirements
                </p>
              </div>

              {/* Input Card */}
              <div
                className="rounded-[20px] p-5 transition-all duration-200"
                style={{
                  width: "820px",
                  minHeight: "130px",
                  backgroundColor: "#162033",
                  border: isFocused
                    ? "1px solid rgba(124, 92, 252, 0.4)"
                    : "1px solid #1E2D45",
                  boxShadow: isFocused
                    ? "0 0 0 1px rgba(124, 92, 252, 0.4), 0 0 40px rgba(124, 92, 252, 0.15)"
                    : "0 4px 24px rgba(0, 0, 0, 0.3)",
                }}
                onMouseEnter={(e) => {
                  if (!isFocused) {
                    e.currentTarget.style.borderColor =
                      "rgba(124, 92, 252, 0.4)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isFocused) {
                    e.currentTarget.style.borderColor =
                      "#1E2D45";
                  }
                }}
              >
                <textarea
                  placeholder="Apa pertanyaan anda saat ini?"
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  className="w-full bg-transparent border-none outline-none resize-none"
                  style={{
                    fontSize: "15px",
                    color: "#F1F5F9",
                    lineHeight: 1.6,
                    minHeight: "50px",
                  }}
                />

                {/* Bottom Toolbar */}
                <div className="flex items-center justify-between mt-3">
                  {/* Left Group */}
                  <div className="flex items-center gap-2">
                    <button
                      className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                      style={{
                        width: "36px",
                        height: "36px",
                        backgroundColor: "#0F1829",
                        color: "#94A3B8",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#1C2840";
                        e.currentTarget.style.color = "#F1F5F9";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#0F1829";
                        e.currentTarget.style.color = "#94A3B8";
                      }}
                    >
                      <Plus size={18} />
                    </button>
                    <button
                      className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                      style={{
                        width: "36px",
                        height: "36px",
                        backgroundColor: "#0F1829",
                        color: "#94A3B8",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#1C2840";
                        e.currentTarget.style.color = "#F1F5F9";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#0F1829";
                        e.currentTarget.style.color = "#94A3B8";
                      }}
                    >
                      <FileText size={18} />
                    </button>
                  </div>

                  {/* Right Group */}
                  <div className="flex items-center gap-2.5">
                    <div
                      className="px-3 rounded-[20px] animate-pulse"
                      style={{
                        height: "28px",
                        border: "1px solid #1E2D45",
                        fontSize: "12px",
                        color: "#475569",
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      Legal AI v1.0
                    </div>
                    <button
                      className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                      style={{
                        width: "36px",
                        height: "36px",
                        backgroundColor: "#0F1829",
                        color: "#94A3B8",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "rgba(124, 92, 252, 0.1)";
                        e.currentTarget.style.color = "#7C5CFC";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#0F1829";
                        e.currentTarget.style.color = "#94A3B8";
                      }}
                    >
                      <Mic size={18} />
                    </button>
                    <button
                      className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                      style={{
                        width: "36px",
                        height: "36px",
                        backgroundColor: "#7C5CFC",
                        color: "white",
                        boxShadow: isFocused
                          ? "0 4px 16px rgba(124, 92, 252, 0.5)"
                          : "none",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#8B6EFD";
                        e.currentTarget.style.boxShadow =
                          "0 4px 16px rgba(124, 92, 252, 0.5)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor =
                          "#7C5CFC";
                        e.currentTarget.style.boxShadow =
                          isFocused
                            ? "0 4px 16px rgba(124, 92, 252, 0.5)"
                            : "none";
                      }}
                    >
                      <Send size={18} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Quick Action Bento Grid */}
              <div className="mt-5" style={{ width: "820px" }}>
                {/* Row 1 */}
                <div className="flex gap-3 mb-3">
                  {/* Card A - Pembuatan Dokumen */}
                  <button
                    onMouseEnter={() => setHoveredCard(1)}
                    onMouseLeave={() => setHoveredCard(null)}
                    className="flex items-center gap-3 px-5 rounded-2xl transition-all duration-200"
                    style={{
                      width: "340px",
                      height: "72px",
                      backgroundColor: "#162033",
                      border:
                        showAllCardHovers || hoveredCard === 1
                          ? `1px solid ${quickActions[0].borderColor}`
                          : "1px solid #1E2D45",
                      boxShadow:
                        showAllCardHovers || hoveredCard === 1
                          ? `0 0 24px ${quickActions[0].glowColor}`
                          : "none",
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        filter:
                          showAllCardHovers || hoveredCard === 1
                            ? `drop-shadow(0 0 10px ${quickActions[0].color})`
                            : "none",
                      }}
                    >
                      <FilePlus
                        size={22}
                        style={{ color: quickActions[0].color }}
                      />
                    </div>
                    <div className="flex flex-col items-start gap-0.5">
                      <div
                        style={{
                          fontSize: "14px",
                          fontWeight: 600,
                          color: "#F1F5F9",
                        }}
                      >
                        {quickActions[0].title}
                      </div>
                      <div
                        style={{
                          fontSize: "12px",
                          color: "#475569",
                        }}
                      >
                        {quickActions[0].subtitle}
                      </div>
                    </div>
                  </button>

                  {/* Card B - Perbandingan Dokumen */}
                  <button
                    onMouseEnter={() => setHoveredCard(2)}
                    onMouseLeave={() => setHoveredCard(null)}
                    className="flex items-center gap-3 px-5 rounded-2xl transition-all duration-200 flex-1"
                    style={{
                      height: "72px",
                      backgroundColor: "#162033",
                      border:
                        showAllCardHovers || hoveredCard === 2
                          ? `1px solid ${quickActions[1].borderColor}`
                          : "1px solid #1E2D45",
                      boxShadow:
                        showAllCardHovers || hoveredCard === 2
                          ? `0 0 24px ${quickActions[1].glowColor}`
                          : "none",
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        filter:
                          showAllCardHovers || hoveredCard === 2
                            ? `drop-shadow(0 0 10px ${quickActions[1].color})`
                            : "none",
                      }}
                    >
                      <GitCompare
                        size={22}
                        style={{ color: quickActions[1].color }}
                      />
                    </div>
                    <div className="flex flex-col items-start gap-0.5">
                      <div
                        style={{
                          fontSize: "14px",
                          fontWeight: 600,
                          color: "#F1F5F9",
                        }}
                      >
                        {quickActions[1].title}
                      </div>
                      <div
                        style={{
                          fontSize: "12px",
                          color: "#475569",
                        }}
                      >
                        {quickActions[1].subtitle}
                      </div>
                    </div>
                  </button>
                </div>

                {/* Row 2 */}
                <div className="flex gap-3">
                  {/* Card C - Kepatuhan Dokumen */}
                  <button
                    onMouseEnter={() => setHoveredCard(3)}
                    onMouseLeave={() => setHoveredCard(null)}
                    className="flex items-center gap-3 px-5 rounded-2xl transition-all duration-200 flex-1"
                    style={{
                      height: "72px",
                      backgroundColor: "#162033",
                      border:
                        showAllCardHovers || hoveredCard === 3
                          ? `1px solid ${quickActions[2].borderColor}`
                          : "1px solid #1E2D45",
                      boxShadow:
                        showAllCardHovers || hoveredCard === 3
                          ? `0 0 24px ${quickActions[2].glowColor}`
                          : "none",
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        filter:
                          showAllCardHovers || hoveredCard === 3
                            ? `drop-shadow(0 0 10px ${quickActions[2].color})`
                            : "none",
                      }}
                    >
                      <ShieldCheck
                        size={22}
                        style={{ color: quickActions[2].color }}
                      />
                    </div>
                    <div className="flex flex-col items-start gap-0.5">
                      <div
                        style={{
                          fontSize: "14px",
                          fontWeight: 600,
                          color: "#F1F5F9",
                        }}
                      >
                        {quickActions[2].title}
                      </div>
                      <div
                        style={{
                          fontSize: "12px",
                          color: "#475569",
                        }}
                      >
                        {quickActions[2].subtitle}
                      </div>
                    </div>
                  </button>

                  {/* Card D - Analisis Kontrak */}
                  <button
                    onMouseEnter={() => setHoveredCard(4)}
                    onMouseLeave={() => setHoveredCard(null)}
                    className="flex items-center gap-3 px-5 rounded-2xl transition-all duration-200"
                    style={{
                      width: "340px",
                      height: "72px",
                      backgroundColor: "#162033",
                      border:
                        showAllCardHovers || hoveredCard === 4
                          ? `1px solid ${quickActions[3].borderColor}`
                          : "1px solid #1E2D45",
                      boxShadow:
                        showAllCardHovers || hoveredCard === 4
                          ? `0 0 24px ${quickActions[3].glowColor}`
                          : "none",
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        filter:
                          showAllCardHovers || hoveredCard === 4
                            ? `drop-shadow(0 0 10px ${quickActions[3].color})`
                            : "none",
                      }}
                    >
                      <Scale
                        size={22}
                        style={{ color: quickActions[3].color }}
                      />
                    </div>
                    <div className="flex flex-col items-start gap-0.5">
                      <div
                        style={{
                          fontSize: "14px",
                          fontWeight: 600,
                          color: "#F1F5F9",
                        }}
                      >
                        {quickActions[3].title}
                      </div>
                      <div
                        style={{
                          fontSize: "12px",
                          color: "#475569",
                        }}
                      >
                        {quickActions[3].subtitle}
                      </div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
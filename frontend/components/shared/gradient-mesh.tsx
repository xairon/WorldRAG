"use client"

export function GradientMesh() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden>
      <div
        className="absolute w-[600px] h-[600px] rounded-full animate-[drift1_20s_ease-in-out_infinite]"
        style={{ background: "var(--mesh-1)", filter: "blur(120px)", top: "-10%", left: "-5%" }}
      />
      <div
        className="absolute w-[500px] h-[500px] rounded-full animate-[drift2_25s_ease-in-out_infinite]"
        style={{ background: "var(--mesh-2)", filter: "blur(120px)", top: "40%", right: "-10%" }}
      />
      <div
        className="absolute w-[400px] h-[400px] rounded-full animate-[drift3_22s_ease-in-out_infinite]"
        style={{ background: "var(--mesh-3)", filter: "blur(120px)", bottom: "-5%", left: "30%" }}
      />
    </div>
  )
}

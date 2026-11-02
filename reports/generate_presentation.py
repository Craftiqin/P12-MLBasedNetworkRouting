from pathlib import Path
import csv
import math

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/IoT_Mesh_Intelligent_Routing_Presentation.pptx"
NAVY = "101D32"; PANEL = "182A43"; PANEL2 = "203650"; WHITE = "F4F7FB"
MUTED = "AAB9CC"; TEAL = "39D6C4"; BLUE = "69A9FF"; ORANGE = "FFB454"
RED = "FF7777"; GREEN = "75D6A1"; LINE = "314762"
SW, SH = 13.333, 7.5

prs = Presentation(); prs.slide_width = Inches(SW); prs.slide_height = Inches(SH)
prs.core_properties.title = "Machine Learning-Based Intelligent Routing Optimization for Low-Power IoT Mesh Networks"
prs.core_properties.subject = "M.Tech project review — evidence-bound project status"
prs.core_properties.author = "Project team"
blank = prs.slide_layouts[6]

def rgb(h): return RGBColor.from_string(h)
def rect(slide, x,y,w,h, color=PANEL, radius=True, line=None):
    sh=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb=rgb(color); sh.line.fill.background() if not line else None
    if line: sh.line.color.rgb=rgb(line); sh.line.width=Pt(1)
    if radius:
        try: sh.adjustments[0]=0.12
        except Exception: pass
    return sh
def txt(slide, text, x,y,w,h, size=16, color=WHITE, bold=False, font="Aptos", align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE, margin=0.04):
    box=slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf=box.text_frame; tf.clear(); tf.word_wrap=True
    tf.margin_left=Inches(margin); tf.margin_right=Inches(margin); tf.margin_top=Inches(margin); tf.margin_bottom=Inches(margin); tf.vertical_anchor=valign
    for i,line in enumerate(str(text).split("\n")):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph(); p.text=line; p.alignment=align; p.space_after=Pt(3)
        for r in p.runs: r.font.name=font; r.font.size=Pt(size); r.font.bold=bold; r.font.color.rgb=rgb(color)
    return box
def line(slide,x1,y1,x2,y2,color=LINE,width=2,dash=None):
    s=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)); s.line.color.rgb=rgb(color); s.line.width=Pt(width)
    if dash: s.line.dash_style=dash
    return s
def pill(slide,label,x,y,w,color=TEAL):
    rect(slide,x,y,w,.31,color); txt(slide,label,x+.06,y+.01,w-.12,.27,9,NAVY,True,align=PP_ALIGN.CENTER)
def base(title, section="PROJECT REVIEW", sub=None):
    s=prs.slides.add_slide(blank); s.background.fill.solid(); s.background.fill.fore_color.rgb=rgb(NAVY)
    rect(s,0,0,.11,SH,TEAL,False)
    txt(s,section.upper(),.48,.22,5,.24,9,TEAL,True)
    txt(s,title,.48,.52,12.2,.55,25,WHITE,True)
    if sub: txt(s,sub,.5,1.13,12,.36,11,MUTED)
    line(s,.48,7.04,12.84,7.04,LINE,1)
    txt(s,"P12 · INTELLIGENT IoT MESH ROUTING",.5,7.1,7,.2,8,MUTED)
    txt(s,f"{len(prs.slides):02d}",12.25,7.08,.55,.22,9,MUTED,True,align=PP_ALIGN.RIGHT)
    return s
def card(s,x,y,w,h,heading,body,accent=TEAL,fs=14):
    rect(s,x,y,w,h,PANEL)
    rect(s,x,y,.06,h,accent,False)
    txt(s,heading,x+.2,y+.13,w-.4,.38,15,accent,True)
    txt(s,body,x+.2,y+.59,w-.4,h-.7,fs,WHITE,valign=MSO_ANCHOR.TOP)
def bullets(s,items,x,y,w,h,fs=17,color=WHITE):
    text="\n".join("•  "+a for a in items)
    return txt(s,text,x,y,w,h,fs,color,valign=MSO_ANCHOR.TOP,margin=.08)
def node(s,x,y,label,kind="relay",sub=None,w=1.35,h=.72):
    color={"gateway":GREEN,"source":ORANGE,"relay":BLUE,"ml":TEAL,"laptop":PANEL2}.get(kind,BLUE)
    rect(s,x,y,w,h,PANEL2,True,color); txt(s,label,x+.06,y+.09,w-.12,.28,12,WHITE,True,align=PP_ALIGN.CENTER)
    if sub: txt(s,sub,x+.04,y+.4,w-.08,.22,8,MUTED,align=PP_ALIGN.CENTER)
def photo_placeholder(s,x,y,w,h,caption):
    sh=rect(s,x,y,w,h,"14243A",True,LINE); sh.line.dash_style=2
    txt(s,"PHOTO PLACEHOLDER",x+.2,y+h*.36,w-.4,.3,12,TEAL,True,align=PP_ALIGN.CENTER)
    txt(s,caption,x+.2,y+h*.53,w-.4,.42,10,MUTED,align=PP_ALIGN.CENTER)
def add_table(s, rows, x,y,w,h, widths=None, fs=11):
    r=len(rows); c=len(rows[0]); sh=s.shapes.add_table(r,c, Inches(x), Inches(y), Inches(w), Inches(h)); t=sh.table
    if widths:
        for j,v in enumerate(widths): t.columns[j].width=Inches(v)
    for i,row in enumerate(rows):
        for j,val in enumerate(row):
            cell=t.cell(i,j); cell.text=str(val); cell.fill.solid(); cell.fill.fore_color.rgb=rgb(PANEL2 if i==0 else PANEL if i%2 else "1B304A")
            cell.margin_left=Inches(.09); cell.margin_right=Inches(.06); cell.margin_top=Inches(.04); cell.margin_bottom=Inches(.04)
            cell.vertical_anchor=MSO_ANCHOR.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.alignment=PP_ALIGN.LEFT
                for rr in p.runs: rr.font.name="Aptos"; rr.font.size=Pt(fs); rr.font.bold=(i==0); rr.font.color.rgb=rgb(TEAL if i==0 else WHITE)
    return sh

# 1
s=prs.slides.add_slide(blank); s.background.fill.solid(); s.background.fill.fore_color.rgb=rgb(NAVY); rect(s,0,0,.15,SH,TEAL,False)
node(s,7.8,1.05,"SOURCE","source"); node(s,9.5,2.35,"RELAY A","relay"); node(s,7.7,3.8,"RELAY B","relay"); node(s,10.9,3.8,"GATEWAY","gateway")
line(s,8.65,1.75,9.68,2.5,LINE,1); line(s,8.1,1.75,8.0,3.8,LINE,1)
line(s,10.7,2.8,11.3,3.8,LINE,1); line(s,9.05,4.18,10.9,4.18,LINE,1)
txt(s,"M.Tech Final-Year Project",.8,.72,5,.35,12,TEAL,True)
txt(s,"Machine Learning-Based\nIntelligent Routing Optimization",.8,1.35,7.0,1.65,30,WHITE,True)
txt(s,"for Low-Power IoT Mesh Networks",.82,3.08,6.6,.5,20,MUTED)
line(s,.82,4.0,5.8,4.0,TEAL,3)
txt(s,"Project review presentation",.82,4.27,5,.4,15,WHITE,True)
txt(s,"Student / guide / institution details not supplied in project synopsis",.82,5.85,6.8,.45,10,MUTED)
txt(s,"01",12.1,7.06,.65,.2,9,MUTED,align=PP_ALIGN.RIGHT)

# 2–9
s=base("From problem to validation", "PRESENTATION MAP")
for i,(h,b) in enumerate([("01–06 · Context","Problem, motivation, objectives"),("07–09 · Solution","Baseline, proposal, requirements"),("10–15 · Hardware","Architecture, roles, power boundary"),("16–20 · Intelligence","Software, routing, model, decision flow"),("21–25 · Evidence","Simulation status, metrics, limitations"),("26–30 · Next phase","Hardware plan, validation, close")]):
    x=.55+(i%3)*4.15; y=1.65+(i//3)*2.25; card(s,x,y,3.8,1.78,h,b,[TEAL,BLUE,ORANGE][i%3],14)
s=base("IoT mesh: reach through cooperation", "A · INTRODUCTION", "Multi-hop forwarding extends coverage when a node cannot reach gateway directly.")
node(s,.9,2.5,"SENSOR","source"); node(s,3.2,1.65,"RELAY 1"); node(s,3.2,3.45,"RELAY 2"); node(s,5.7,2.5,"RELAY 3"); node(s,8.2,2.5,"GATEWAY","gateway")
for a in [(2.25,2.85,3.2,2.0),(2.25,2.85,3.2,3.8),(4.55,2,5.7,2.85),(4.55,3.8,5.7,2.85),(7.05,2.85,8.2,2.85)]: line(s,*a,TEAL,2)
card(s,9.9,1.65,2.7,3.6,"Why low power?","• Battery / constrained supply\n• Small packets, intermittent sensing\n• Every relay spends energy\n• Link quality varies over time",ORANGE,14)
s=base("Routing must balance competing costs", "A · PROBLEM", "A shortest path may contain a weak link; a reliability-first detour may add hops and delay.")
for i,(h,b,c) in enumerate([("ENERGY","Relay transmissions consume scarce node energy.",ORANGE),("RELIABILITY","Lossy links reduce end-to-end delivery.",RED),("LATENCY","Longer detours can increase packet delay.",BLUE),("LIFETIME","Uneven forwarding load can drain relays sooner.",TEAL)]):
    card(s,.65+i*3.15,2,2.85,2.65,h,b,c,16)
txt(s,"Project question",.8,5.35,2,.35,13,TEAL,True); txt(s,"Can measured link conditions guide better next-hop choices than a conventional baseline?",2.55,5.23,9.7,.65,19,WHITE,True)
s=base("Motivation: adapt when conditions change", "A · MOTIVATION")
card(s,.65,1.7,3.8,3.8,"Fixed metric","Minimum-hop is simple and deterministic. It may keep choosing a short path when a link degrades.",BLUE,17)
card(s,4.75,1.7,3.8,3.8,"Adaptive signal","RSSI, delay, loss, throughput and remaining hops describe changing candidate links.",TEAL,17)
card(s,8.85,1.7,3.8,3.8,"Engineering test","Compare baseline and ML-assisted decisions under paired, repeatable conditions; report wins and regressions.",ORANGE,16)
s=base("Objectives and success evidence", "A · OBJECTIVES")
items=[("01","Build multi-hop ESP32 network","Physical testbed; pending"),("02","Measure link and delivery metrics","RSSI / RTT / loss / throughput / hops"),("03","Train lightweight supervised model","Decision Tree is software-phase model"),("04","Use guarded next-hop selection","Loop checks, hop limit, hysteresis, fallback"),("05","Compare against conventional routing","Paired trials; measured benefit not assumed")]
for i,(n,h,b) in enumerate(items):
    y=1.5+i*1.02; pill(s,n,.72,y,.52,TEAL); txt(s,h,1.55,y,5,.37,15,WHITE,True); txt(s,b,6.7,y,5.6,.38,12,MUTED)
s=base("Project baseline and reference idea", "B · EXISTING APPROACHES", "Repository implementation compares deterministic minimum-hop with an ML-assisted next-hop scorer.")
add_table(s,[["Approach","Strength","Limit / boundary"],["Minimum-hop baseline","Simple, deterministic","Ignores predicted delivery quality"],["ML-assisted scorer","Ranks valid candidates using predicted ACK success + tail cost","Synthetic features today; hardware data pending"],["ML-RPL reference","CatBoost + RPL parent selection in cited paper","Inspiration only; not reproduced here"]],.65,1.65,12,3.4,[2.3,4.2,5.5],12)
txt(s,"No fabricated literature survey. One verified reference is listed on slide 30.",.75,5.45,11,.35,11,MUTED)
s=base("Proposed solution: measure → score → forward", "B · PROPOSED SYSTEM")
for i,(h,b) in enumerate([("Observe","Neighbor link metrics"),("Predict","P(next-hop ACK success)"),("Score","Link risk + remaining path cost"),("Guard","Loop / hop limit / hysteresis"),("Forward","Use selected relay; log outcome")]):
    x=.55+i*2.55; card(s,x,2,2.2,2.2,h,b,[BLUE,TEAL,ORANGE,RED,GREEN][i],13)
    if i<4: line(s,x+2.2,3.1,x+2.5,3.1,TEAL,2)
txt(s,"Software evidence: Python simulator + Decision Tree. Physical ESP32 routing and INET ML integration: planned.",.8,5.15,11.5,.65,15,WHITE,True,align=PP_ALIGN.CENTER)
s=base("Scope and requirements", "B · BOUNDARIES")
card(s,.7,1.65,3.85,4.35,"Functional","• Multi-hop source → gateway\n• Neighbor/link observations\n• Candidate route selection\n• Duplicate / loop safeguards\n• Baseline comparison",TEAL,15)
card(s,4.75,1.65,3.85,4.35,"Planned hardware","• 4–6 ESP32 boards\n• ESP-NOW direct peer transport\n• Application-level forwarding\n• Laptop for logs / offline ML\n• Board / wiring exacts TBD",BLUE,15)
card(s,8.8,1.65,3.85,4.35,"Project boundaries","• Small controlled testbed\n• Not standards-compliant RPL\n• No physical measurements yet\n• Energy gains unproven\n• No ML in INET baseline",ORANGE,15)

# 10–15
s=base("System architecture: hardware path and evaluation loop", "C · ARCHITECTURE", "Hardware plan is distinct from the completed earlier Python simulation stage.")
node(s,.7,2.2,"SOURCE","source", "ESP32 · packets"); node(s,3.0,1.5,"RELAY A"); node(s,3.0,3.15,"RELAY B"); node(s,5.5,2.2,"GATEWAY","gateway","ESP32 logger")
line(s,2.05,2.55,3,1.85,TEAL); line(s,2.05,2.55,3,3.5,TEAL); line(s,4.35,1.85,5.5,2.55,TEAL); line(s,4.35,3.5,5.5,2.55,TEAL)
rect(s,7.45,1.45,4.8,1.1,PANEL); txt(s,"CSV observations + delivery labels",7.7,1.72,4.3,.5,15,WHITE,True,align=PP_ALIGN.CENTER)
rect(s,7.45,3.15,2.1,1.15,PANEL); txt(s,"Offline model\ntraining",7.65,3.4,1.7,.55,13,WHITE,True,align=PP_ALIGN.CENTER)
rect(s,10.15,3.15,2.1,1.15,PANEL); txt(s,"Firmware inference\n(planned)",10.35,3.4,1.7,.55,12,TEAL,True,align=PP_ALIGN.CENTER)
line(s,6.85,2.55,7.45,2.0,BLUE); line(s,9.85,2.0,8.5,3.15,BLUE); line(s,9.55,3.72,10.15,3.72,ORANGE); line(s,10.15,4.0,6.85,2.85,ORANGE,1)
txt(s,"Arrows show planned observation/training loop; inference return path needs firmware implementation.",.75,5.4,11,.38,11,MUTED)
s=base("Hardware roles and evidence status", "C · HARDWARE")
add_table(s,[["Component","Role","Status / interface"],["ESP32 development boards (4–6)","Source, relay(s), gateway","Specified in synopsis; exact board / radio API TBD"],["ESP-NOW link","Direct peer transport","Proposed; not itself multi-hop routing"],["USB / stable power","Programming and bench power","Planned; no electrical schematic / pin map"],["Laptop","Firmware build, serial logging, Python ML","Specified; toolchain choice ESP-IDF / Arduino TBD"]],.65,1.55,12,3.65,[3.0,3.25,5.75],12)
photo_placeholder(s,.8,5.45,2.8,1.1,"Add real board/component photo")
photo_placeholder(s,3.85,5.45,2.8,1.1,"Add real interconnection photo")
txt(s,"No boards, sensors, battery, or pin assignments documented as selected.",7,5.7,5,.5,12,ORANGE,True)
s=base("Node architecture: keep routing above radio callbacks", "C · NODE DESIGN")
for i,(h,b,c) in enumerate([("Power","USB / future battery; measure current",ORANGE),("Radio","ESP-NOW peer send/receive",BLUE),("Forwarding","Frame checks, dedupe, hop-limit, path",TEAL),("Route engine","Feature vector → model → guarded next hop",GREEN)]):
    y=1.55+i*1.08; card(s,.85,y,4.2,.82,h,b,c,12)
    if i<3: line(s,2.95,y+.82,2.95,y+1.05,LINE,2)
photo_placeholder(s,6.05,1.65,5.9,3.8,"Insert actual assembled node; label board + antenna + power")
txt(s,"No sensing payload component specified in the project design. Node is treated as a packet source / relay / gateway.",.95,6.15,11.5,.35,11,MUTED)
s=base("Two candidate corridors enable alternate forwarding", "C · TOPOLOGY", "Concept adapted from the project’s six-node Python graph and INET configuration; labels simplified.")
node(s,.65,2.5,"SOURCE","source",w=1.5); node(s,3,1.5,"A1"); node(s,5.6,1.5,"A2"); node(s,3,3.55,"B1"); node(s,5.6,3.55,"B2"); node(s,9.1,2.5,"GATEWAY","gateway",w=1.5)
for a in [(2.15,2.85,3,1.85),(2.15,2.85,3,3.9),(4.35,1.85,5.6,1.85),(4.35,3.9,5.6,3.9),(6.95,1.85,9.1,2.85),(6.95,3.9,9.1,2.85)]: line(s,*a,TEAL,2)
line(s,4.35,1.85,5.6,3.9,LINE,1); line(s,4.35,3.9,5.6,1.85,LINE,1)
pill(s,"ACTIVE ROUTE (illustrative)",.8,5.4,2.6,TEAL); pill(s,"ALTERNATE PATH",3.65,5.4,2.1,BLUE)
txt(s,"Illustration of candidate corridors, not a measured radio topology.",6.1,5.43,5.5,.3,11,MUTED)
s=base("Interfaces: what is defined vs still open", "C · INTERCONNECTIONS")
add_table(s,[["Boundary","Documented data / behavior","Open implementation detail"],["ESP32 ↔ ESP32","ESP-NOW direct peer transport proposed","Board model, channel, peer setup, antenna"],["Application packet","IDs, sequence, timestamp, hop count/limit, payload, path history","Binary frame layout, size, integrity protection"],["Metrics ↔ route engine","RSSI, RTT, loss, throughput, hop count proposed","Sampling windows, smoothing, missing-data policy"],["Gateway ↔ laptop","Serial or Wi-Fi logging proposed; CSV output","Connector, schema, time sync"]],.55,1.55,12.2,4.2,[2.15,5.05,5.0],11)
txt(s,"No GPIO / UART pin mapping provided. Add only after board and firmware stack are selected.",.7,6.1,11.6,.35,12,ORANGE,True)
s=base("Energy-aware goal; energy measurement absent", "C · POWER")
card(s,.7,1.65,3.75,3.7,"Design constraint","Relay radio activity and forwarding load draw energy. Balance route quality against resource use.",ORANGE,16)
card(s,4.8,1.65,3.75,3.7,"Current evidence","Simulator has no battery/current model. CSV outputs do not include energy. No physical current readings.",RED,16)
card(s,8.9,1.65,3.75,3.7,"Validation need","Add current measurement; report board, voltage, sampling method, workload, duration and uncertainty.",TEAL,15)
txt(s,"Do not claim lifetime or energy improvement from packet-delivery metrics alone.",1.0,5.85,11.2,.38,14,WHITE,True,align=PP_ALIGN.CENTER)

#16–20
s=base("Software stages and module boundaries", "D · SOFTWARE")
add_table(s,[["Layer","Repository modules","Role / maturity"],["Experiment UI","app.py · Streamlit / Plotly","Interactive Python simulation dashboard"],["Experiment runner","experiments/runner.py","Paired seeds, seven scenarios, aggregate CSV"],["Simulator + metrics","simulator/core.py · metrics/core.py","Seeded graph packet forwarding; synthetic link values"],["Routing + ML","routing/engines.py · ml/pipeline.py","Minimum-hop; Decision Tree ACK predictor"],["Packet-level simulator","omnetpp-inet/ (NED / INI / XML)","AODV six-node baseline; build/run unverified"]],.62,1.5,12.1,4.5,[2.2,4.2,5.7],11)
s=base("Routing algorithm in software phase", "D · ROUTING", "Python ML scorer; distinct from the OMNeT++ AODV baseline.")
steps=[("1","List neighbors"),("2","Reject down / loop / no-tail candidates"),("3","Predict one-link ACK success"),("4","Cost = 1 − P + remaining-path risk"),("5","Apply 0.08 switch margin"),("6","Forward; minimum-hop fallback")]
for i,(n,b) in enumerate(steps):
    col=i%3; row=i//3; x=.65+col*4.2; y=1.65+row*2.1
    pill(s,n,x,y,.5,TEAL); card(s,x+.65,y-.05,3.35,1.45,b,"Python implementation",[BLUE,RED,TEAL,ORANGE,GREEN,BLUE][i],13)
txt(s,"No custom ML routing is present in INET configuration; it uses AODV.",.85,6.1,11.5,.35,12,ORANGE,True,align=PP_ALIGN.CENTER)
s=base("Decision Tree predicts one link attempt outcome", "D · ML METHOD", "Project software model is a scikit-learn DecisionTreeClassifier; ESP32 deployment not implemented.")
features=["RSSI (dBm)","Latency (ms)","Loss estimate","Throughput (kbps)","Remaining hops"]
for i,f in enumerate(features): pill(s,f,.65,1.65+i*0.73,2.0,[BLUE,TEAL,ORANGE,GREEN,BLUE][i])
line(s,2.8,3.5,4.0,3.5,TEAL,2)
card(s,4.0,2.2,3.1,2.6,"Decision Tree","Depth ≤ 6\nBalanced classes\nPython inference",TEAL,16)
line(s,7.1,3.5,8.15,3.5,TEAL,2)
card(s,8.15,2.2,4.2,2.6,"Output","P(ACK success on candidate link)\nUsed as one-hop risk; tail success estimated separately.",ORANGE,15)
txt(s,"Tree trained on synthetic observations from Python simulator; not the INET model and not firmware-ready.",.8,5.75,11.5,.45,12,MUTED,align=PP_ALIGN.CENTER)
s=base("Dataset is synthetic; real labels are future work", "D · DATASET")
card(s,.65,1.6,3.8,3.8,"Generated dataset","60 runs × 90 observations/run in generator; 5,400 rows. Synthetic link conditions and ACK outcomes.",ORANGE,15)
card(s,4.75,1.6,3.8,3.8,"Features / target","RSSI, latency, loss estimate, throughput, remaining hops → binary success on one simulated link attempt.",TEAL,15)
card(s,8.85,1.6,3.8,3.8,"Evaluation split","Whole runs held out; stored metadata says runs 0–44 train, 45–59 test (strong condition only). Synthetic labels limit transfer.",BLUE,14)
txt(s,"Stored model metadata: failure recall 0.00 on held-out strong-link condition. Accuracy alone would hide this failure-class weakness.",.8,5.85,11.8,.45,13,RED,True,align=PP_ALIGN.CENTER)
s=base("Decision flow includes safeguards and fallbacks", "D · INTEGRATION")
labels=[("Recent metrics","RSSI / RTT / loss / rate"),("Candidate filter","available · no loop · hop limit"),("Model score","P(success) per link"),("Route score","link risk + tail cost"),("Switch gate","margin + dwell confirmation"),("Forward + log","packet ID · path · reason")]
for i,(h,b) in enumerate(labels):
    x=.5+i*2.12; card(s,x,2.15,1.85,2.2,h,b,[BLUE,RED,TEAL,ORANGE,GREEN,BLUE][i],12)
    if i<5: line(s,x+1.85,3.22,x+2.08,3.22,TEAL,2)
txt(s,"Implemented in Python: candidate checks, cost + 0.08 hysteresis and fallback. Dwell confirmation / firmware logging: planned integration.",.8,5.15,11.7,.7,13,WHITE,align=PP_ALIGN.CENTER)

#21–25
s=base("Two simulation stages; neither proves physical behavior", "E · METHODOLOGY")
card(s,.65,1.65,5.75,3.8,"Earlier Python stage · outputs present","Seeded graph packet simulator, synthetic links, seven scenarios, paired algorithm seeds. `outputs/` contains trial + aggregate CSVs. Software-only abstraction.",TEAL,15)
card(s,6.8,1.65,5.75,3.8,"Current packet-level stage · unverified","OMNeT++ / INET AODV six-router NED/INI + scenarios. Required tools absent per repo README; build/run and result generation unverified.",ORANGE,15)
txt(s,"No OMNeT++ ML comparison: INET uses AODV and has no custom ML decision logic.",.8,5.9,11.7,.4,13,RED,True,align=PP_ALIGN.CENTER)
s=base("Scenario plan and execution evidence", "E · SCENARIOS")
add_table(s,[["Scenario group","Python outputs","INET configs"],["Normal / degraded","Present in aggregate CSV","Normal / DegradedPath"],["Loss / latency / load","Present: high_loss, high_latency, congestion","IncreasedPacketLoss / HighLatency / Congestion / IncreasedInterference"],["Failure / recovery","Present: preferred_link_failure, recovery","RelayFailure / PreferredPathFailure / LinkRecovery"],["Node / traffic parameters","Configured in Python runner; outputs indicate 6 nodes, 100 packets/trial, 5 trials","6 routers; 128 B source UDP every 200 ms; 2–58 s; fixed seed-set 17"],["Execution confidence","CSV values exist; run provenance not independently reproduced in this task","Build, execution, traces, result values unverified"]],.52,1.45,12.3,4.75,[2.2,4.5,5.6],10)
s=base("Metrics: define denominator and measurement method", "E · EVALUATION")
add_table(s,[["Metric","Definition / method","Evidence status"],["PDR / loss","Gateway received ÷ generated; loss = 1 − PDR","Python CSV; INET exporter planned"],["End-to-end delay","Source send → gateway receive; delivered packets only","Python sim-time; INET scalar recording configured"],["Throughput","Delivered payload bits ÷ observation duration","Python CSV; INET stats configured"],["Route changes / recovery","Trace chosen next hops over time; time to resumed delivery","Python simulation outputs; INET needs .rt + packet traces"],["Energy / lifetime","Current / power instrumented across workload","Not measured; needs physical instrumentation"]],.58,1.55,12.1,4.45,[2.15,6.1,3.85],11)
s=base("Simulation results: degraded-link case", "E · SAVED PYTHON OUTPUTS", "Earlier Python simulation aggregate CSV · 5 paired trials per algorithm · synthetic link conditions")
rows=[]
with open(ROOT/'outputs/aggregate_results.csv',newline='') as f:
    rows=list(csv.DictReader(f))
vals={(r['scenario'],r['routing']):float(r['pdr_mean']) for r in rows}
basey=5.25; top=1.85; maxv=1.0
for j,(alg,col) in enumerate([("baseline",BLUE),("ml",TEAL)]):
    v=vals.get(('degraded',alg),0); h=(basey-top)*v
    rect(s,2.15+j*2.3,basey-h,1.15,h,col,True); txt(s,f"{v*100:.1f}%",2.03+j*2.3,basey-h-.42,1.4,.3,14,WHITE,True,align=PP_ALIGN.CENTER)
    txt(s,"Minimum-hop" if j==0 else "ML-assisted",1.75+j*2.3,5.4,1.95,.32,11,MUTED,align=PP_ALIGN.CENTER)
line(s,1.55,5.25,7.05,5.25,LINE,1)
for k in range(6):
    y=5.25-k*.68; line(s,1.55,y,7.05,y,LINE,1); txt(s,f"{k*20}%",.72,y-.12,.65,.22,9,MUTED,align=PP_ALIGN.RIGHT)
card(s,7.7,1.85,4.75,3.95,"Read carefully","Saved Python CSV: degraded PDR mean 48.8% baseline vs 83.2% ML (n=5 each). Simulated, not hardware evidence. Aggregate CSV does not by itself prove this specific file was generated from current source revision.",ORANGE,14)
txt(s,"INET packet-level simulation results: none verified / available. Do not conflate these values with OMNeT++.",.8,6.15,11.7,.32,12,RED,True,align=PP_ALIGN.CENTER)
s=base("Evidence supports software behavior only", "E · FINDINGS & LIMITATIONS")
card(s,.65,1.65,3.8,3.8,"Demonstrated in repo","Python code models baseline and ML next-hop selection; outputs exist for paired scenario trials.",TEAL,15)
card(s,4.75,1.65,3.8,3.8,"Not established","Physical ESP32 behavior, radio reliability, energy, and INET execution/results remain unverified.",RED,15)
card(s,8.85,1.65,3.8,3.8,"Threats to validity","Synthetic labels; simplified sequential packets; no MAC contention in Python, calibrated radio, mobility, battery or interference model.",ORANGE,14)
txt(s,"Hardware validation is necessary before claiming deployment performance.",1,5.9,11,.4,14,WHITE,True,align=PP_ALIGN.CENTER)

#26–30
s=base("Planned build sequence for physical prototype", "F · HARDWARE PHASE", "4–6 ESP32 boards proposed. No assembled hardware evidence in repository.")
for i,(n,h,b) in enumerate([("01","Select boards","Confirm model, firmware stack, radio support"),("02","Build fixed route","Source → relay → gateway; packet framing"),("03","Verify safeguards","ACK, IDs, dedupe, hop-limit, loop prevention"),("04","Collect measurements","Beacon / probe windows; log raw data"),("05","Integrate ML","Parity tests, resource limits, fallback")]):
    x=.55+i*2.55; pill(s,n,x,1.55,.52,TEAL); card(s,x,2.0,2.25,2.2,h,b,[BLUE,TEAL,ORANGE,GREEN,BLUE][i],12)
    if i<4: line(s,x+2.25,3.05,x+2.48,3.05,LINE,2)
photo_placeholder(s,.95,4.85,4.9,1.45,"Insert genuine assembled prototype photo")
photo_placeholder(s,6.35,4.85,5.9,1.45,"Insert genuine physical test setup photo")
s=base("Hardware integration and validation checklist", "F · PLANNED TESTS")
tests=["Power-on / board identity / stable logging","Neighbor discovery and bidirectional reachability","Fixed-route end-to-end packet forwarding","Packet ID, duplicate suppression, hop-limit, loop rejection","Baseline vs ML route decision on same workload","Degraded-link route change + recovery; repeat trials","PDR, RTT, throughput, route switches with units and raw logs","Current / energy only with suitable instrumentation"]
for i,t in enumerate(tests):
    x=.8+(i//4)*6.2; y=1.5+(i%4)*1.05; txt(s,"☐",x,y,.35,.35,18,TEAL,True); txt(s,t,x+.5,y,5.4,.58,13,WHITE)
txt(s,"All checks pending; mark complete only with preserved logs / measurements.",.85,6.15,11,.35,12,ORANGE,True,align=PP_ALIGN.CENTER)
s=base("Expected outcomes are hypotheses to test", "F · FUTURE WORK")
card(s,.65,1.65,3.8,3.9,"Expected","Real ESP32 multi-hop forwarding; labelled observations; lightweight inference; repeatable comparison.",TEAL,16)
card(s,4.75,1.65,3.8,3.9,"Enhance","Test more runs / conditions; evaluate class-balanced failure detection; assess model size and inference on target.",BLUE,15)
card(s,8.85,1.65,3.8,3.9,"Then extend","Add energy instrumentation and control overhead; compare with richer routing baselines; explore multiple environments.",ORANGE,15)
txt(s,"Expected outcomes ≠ measured improvements. Report metric trade-offs honestly.",.9,5.95,11.4,.38,13,WHITE,True,align=PP_ALIGN.CENTER)
s=base("Conclusion: a staged path from model to testbed", "SUMMARY")
for i,(h,b,c) in enumerate([("Problem","Fixed routing can miss link changes.",BLUE),("Approach","Predict next-hop ACK success; score valid paths with safeguards.",TEAL),("Current evidence","Python simulation outputs exist; saved degraded-case aggregate favors ML under synthetic conditions.",ORANGE),("Pending","INET run verification, ESP32 firmware, physical measurements and validation.",RED)]):
    card(s,.7,1.5+i*1.1,11.9,.87,h,b,c,13)
txt(s,"Contribution at this stage: a software prototype and a documented, testable hardware integration plan.",.9,6.15,11.4,.35,13,WHITE,True,align=PP_ALIGN.CENTER)
s=base("References · Thank you / questions", "30 · CLOSE")
card(s,.65,1.5,7.25,3.65,"Verified project reference","C. L. Duenas Santos et al., “ML-RPL: Machine Learning-Based Routing Protocol for Wireless Smart Grid Networks,” IEEE Access, vol. 11, pp. 57401–57414, 2023. DOI: 10.1109/ACCESS.2023.3283208.\n\nProject adaptation: ESP32 testbed + lightweight Decision Tree; not reproduction of paper’s CatBoost/RPL system.",TEAL,13)
card(s,8.25,1.5,4.35,3.65,"Project sources","ML_Based_Intelligent_IoT_Mesh_Routing_Synopsis.docx\nREADME.md · ARCHITECTURE.md\ndocs/ESP32_INTEGRATION.md\nomnetpp-inet/README.md + configs\noutputs/aggregate_results.csv\nmodels/delivery_tree.json",BLUE,12)
txt(s,"The PDF named `MiniProject_RCC_v1 (1).pdf` is about datacenter RCC and is unrelated; excluded.",.78,5.55,11.8,.35,11,ORANGE,True,align=PP_ALIGN.CENTER)
txt(s,"THANK YOU",.8,6.05,4.5,.48,25,WHITE,True)
txt(s,"Questions?",5.3,6.05,4.5,.48,25,TEAL,True)

assert len(prs.slides)==30, len(prs.slides)
OUT.parent.mkdir(parents=True,exist_ok=True); prs.save(OUT)
print(f"saved {OUT} ({len(prs.slides)} slides)")

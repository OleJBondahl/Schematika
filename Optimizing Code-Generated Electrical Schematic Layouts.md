# **Optimizing Code-Generated Electrical Schematic Layouts**

[https://gemini.google.com/app/0368f47330ded448](https://gemini.google.com/app/0368f47330ded448)

*User prompt: I really need to improve the layout of my electrical drawings as code software. The code part is working fine, but the drawing generation which produces SVG and then pdf drawings of the electrical circuit and system are not pretty... See the schematika GitHub site. I need to either improve my layout algorithms alot, but i suspect that includes alot of tweaking, or find a service or ai model or something that can lay it out properly, of a symbol library that is well designed for such code based layout. Help me research this*

Response: Auto-layout for electrical schematics is a notoriously hard problem. Pure graph layout engines (like Graphviz or Dagre) treat nodes as points and edges as lines, but **electrical schematics have rigid spatial domain rules**: orthogonal routing, fixed symbol pin orientations, bus routing, page grid snapping, and strict reader flow conventions (power at the top, ground at the bottom, signal left-to-right).

Building these algorithms manually requires handling NP-hard sub-problems (layering, planarization, orthogonal wire routing with obstacle avoidance, and net minimization).

The best path forward involves choosing between specialized open-source layout engines, AI/heuristic models, or symbol libraries.

### **Option 1: Existing Specialized Schematic Libraries & Engines (Recommended)**

Instead of reinventing the layout logic or relying on generic graph tools, consider using engines built specifically for domain-aware circuit layout.

> * **ELK (Eclipse Layout Kernel) \- Layered / Orthogonal Engines:**  
  * **Why it works:** ELK features a specific elk.layered and port-aware routing algorithm (org.eclipse.elk.layered). Unlike standard engines, ELK natively supports **ports (pins on fixed sides of nodes)**, port constraints, and orthogonal routing.  
  * **Stack:** Runs in Java or JavaScript/TypeScript via @eclipse-elk/elm or elkjs.  
> * **Schemdraw (Python):**  
  * **Why it works:** Schemdraw uses a declarative "turtle graphics" model (e.g., d \+= elm.Resistor().right().label('10k')). While it requires explicit directional placement in code rather than pure auto-layout from a netlist, it yields publication-quality, crisp vector/SVG electrical diagrams without complex geometry tweaking.  
> * **NetlistsVG / SKiDL pipeline:**  
  * **Why it works:** NetlistsVG converts Yosys JSON netlists into formatted SVG schematics using skin-based rendering. You can analyze its layout core to see how it assigns topological ranks to electrical components before routing connections orthagonally.

### **Option 2: The Two-Stage Hybrid Approach (Custom Layout)**

If custom routing engine development is necessary, splitting the layout pipeline into two distinct deterministic phases prevents the code from becoming an unmaintainable web of layout hacks:

`[Netlist / Graph] ──► 1. Placement (Grid/Constraint Solver) ──► 2. Orthogonal Wire Routing (A* / Lee) ──► [SVG]`

#### **Phase 1: Grid-Based Placement**

> * **Enforce a strict coordinate grid:** Electrical schematics must snap to a grid (e.g., 10mm×10mm or 0.1 in).  
> * **Force-Directed with Grid Constraints:** Use a force-directed algorithm (like Fruchterman-Reingold), but modify the forces to enforce domain rules:  
  * Apply a vertical directional force: Power rails (*Vcc*​,+24V) pull toward *Y*\=0, Ground (*GND*) pulls toward *Y*\=*Ymax*​.  
  * Apply horizontal flow forces: Input signals pull Left, Output signals pull Right.  
> * **Snapping:** Round all node coordinates to the nearest grid step after force convergence.

#### **Phase 2: Orthogonal Wire Routing (Pathfinding)**

> * Do **not** use straight lines or bezier curves. Use *A Pathfinding on a Grid Map*\* or **Lee's Algorithm**:  
  * Treat placed symbol bounding boxes as obstacles on a grid matrix.  
  * Route wires along grid paths using A\*.  
  * Add path cost penalties for **bends/corners** (e.g., base step cost \= 1, 90° turn penalty \= 5\) to favor long straight lines over jagged zig-zags.  
  * Add penalties for wire overlaps/crossings.

### **Option 3: LLMs and AI Models for Schematic Layout**

While general Vision-LLMs (like GPT-4o) cannot reliably output deterministic, crisp SVG coordinates directly from code without introducing spatial hallucination and floating-point alignment errors, hybrid AI patterns perform well:

> 1. **Code-to-Declarative DSL via LLM:**  
   * Use an LLM (e.g., Claude 3.5 Sonnet or GPT-4o) to translate unstructured electrical descriptions or netlists into structured DSLs (like **Schemdraw** Python scripts or **TikZ / Circuitikz** LaTeX code).  
   * Execute the generated script on the server to render perfectly formatted, publication-ready vector SVGs/PDFs.  
> 2. **GNN / RL Layout Models:**  
   * Research in EDA (Electronic Design Automation) uses Graph Neural Networks (GNNs) paired with Reinforcement Learning (RL) for PCB/schematic placement. However, implementing this for a lightweight software tool usually introduces excessive model training overhead compared to deterministic heuristic engines like ELK.

### **Option 4: Standardized Symbol Libraries & Design Rules**

Visual appeal often stems more from symbol proportions, grid alignment, and typographic hierarchy than complex wire routing.

> * **Acheron Docs \- Electrical Symbol Library:**  
  * An open-source SVG symbol library following IEEE/ANSI standards, built around a strict 1mm grid with explicit pin/anchor alignments.  
> * **Standard Symbol Design Guidelines:**  
  * **Uniform Pin Pitch:** Define a standardized terminal distance (e.g., 20px or 2.54mm) across every component symbol (resistors, relays, microcontrollers) so wires meet pins horizontally/vertically without awkward sub-pixel jogs.  
  * **Layering Strategy:** Keep text (designators like R1, values like 10kΩ) on isolated SVG text layers positioned relative to the symbol's bounding box center.

### **Comparison of Layout Strategies**

| Strategy | Dev Effort | Visual Quality | Best For |
| :---- | :---- | :---- | :---- |
| **elkjs (org.eclipse.elk.layered)** | Low | High | Full programmatic auto-layout from netlists/graph objects. |
| **Schemdraw / Circuitikz Pipeline** | Low | Very High | Direct code-to-schematic generation using declarative direction primitives. |
| *Custom Grid A Router*\* | High | Tailored | High control over custom layout rules and specific visual styling. |
| **LLM \-\> Schemdraw / TikZ Pipeline** | Medium | High | Natural language or loose code-to-diagram workflows. |

**Sources**

> 1. [Electric Symbols \- Acheron Docs](https://acheronproject.com/electric_symbols/electric_symbols/)

---

*User prompt: I can manually split the different circuits belonging to the same cabinet into different pages, and then i need a layout engine to handle the layout on each page. Preferably i would like the engine to also split the entire system into pages. Im currently specifing locations in the code, but that is alot more work sadly. Also in talking about large electrical cabinets with relays, fuses, terminals... Which have strict rules about how they should be drawn. I also have a PCB module, which uses skidl, but also needs a layout for human development and review of the electrical circuits. I have created the symbols in pure code, using a svg drawing library in Python. I would prefer to keep using Python, and not add additional programming languages to the codebase.*

Response: For large-scale electrical control cabinets (relays, PLCs, terminal blocks, fuses) and high-density schematic review, layout automation requires strict compliance with domain rules: signals flow left-to-right, power rails sit vertically or along top/bottom margins, and DIN-rail components group linearly.

When specifying explicit (x, y) coordinates becomes unmanageable, you need a page-budgeting mechanism combined with a constraint-aware layout solver.

### **1\. Page Budgeting and Pagination Architecture**

To handle multi-page cabinet schematics in Python without manual coordinate tracking, split the problem into a two-pass pipeline: **Pagination & Layout Budgeting** followed by **Single-Page Placement & Routing**.

`[ Full System Netlist ]`  
          `│`  
          `▼`  
`1. Page Partitioning Engine (Power domains, Functional modules, Terminal rails)`  
          `│`  
          `├───────────────────────┬───────────────────────┐`  
          `▼                       ▼                       ▼`  
    `[ Page 1 AST ]          [ Page 2 AST ]          [ Page 3 AST ]`  
          `│                       │                       │`  
          `▼                       ▼                       ▼`  
   `2. Single-Page Engine   2. Single-Page Engine   2. Single-Page Engine`  
          `│                       │                       │`  
          `▼                       ▼                       ▼`  
     `[ Page 1 SVG ]          [ Page 2 SVG ]          [ Page 3 SVG ]`

#### **Automatic Page Partitioning Rules**

Instead of placing nodes globally, write a rule-based partitioner in Python to divide the graph into pages based on standard industrial drawing conventions:

> * **Primary Power Distribution:** Main disconnects, fuses, contactors, and transformer primaries belong on Page 1 (or early pages).  
> * **Control & Protection Circuits:** Individual relay coils, PLC I/O banks, and auxiliary switches belong on subsequent pages grouped by functional sub-system.  
> * **Inter-Page Signals (Cross-Referencing):** When a net spans across pages (e.g., control wire going from a PLC output on Page 3 to a contactor coil on Page 5), the partitioner truncates the net and creates **Off-Page Connectors** storing source/destination page and grid coordinates (e.g., /4.B2).

### **2\. Pure Python Engine Alternatives**

To stay entirely within Python and avoid multi-language build chains (like Java for ELK or JS for Node engines), you have three practical paths:

#### **Option A: schemdraw Stack Architecture (High Visual Control)**

schemdraw removes coordinate tracking by using **relative directional placements** (.right(), .down(), .at()).

> * **How it applies to SKiDL:** SKiDL generates a netlist object model in Python. You can write a Python converter function that traverses the SKiDL netlist and generates schemdraw elements.  
> * **Cabinet Symbols:** Because schemdraw elements are defined programmatically using SVG shapes, you can wrap your existing SVG symbol definitions inside custom schemdraw.elements.Element classes.  
> * **Page Boundary Control:** You track the current "draw cursor". When cursor\_x \> MAX\_PAGE\_WIDTH, push the current sub-circuit to a new schemdraw.Drawing() instance (representing the next page) and automatically insert off-page terminal markers.

#### **Option B: Python Wrapper for ELK (elkpy / pyelk)**

If you want **zero directional hints** (pure graph in, schematics out), ELK is the industry standard. While ELK's layout engine runs in Java, elkpy provides a native Python interface via an automated background process or RPC wrapper.

> * **Port Constraints:** ELK allows you to specify fixed pin locations on your Python-generated SVG symbols (e.g., pin 1 on TOP, pin 2 on BOTTOM).  
> * **Directional Enforcement:** Configure layout options directly in Python dicts:  
>   `layout_options = {`  
>       `'elk.direction': 'RIGHT',`  
>       `'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',`  
>       `'elk.edgeRouting': 'ORTHOGONAL',`  
>       `'elk.layered.spacing.nodeNodeBetweenLayers': '50.0'`  
>   `}`

#### **Option C: Custom Constraint Solver with z3-solver or pygraphviz**

For strict control-cabinet rules (e.g., Terminal strip *X*1 must sit at the bottom margin *Y*\=900, Power Rail \+24V must run along *Y*\=100), standard graph engines often fail because they try to minimize overall edge lengths rather than adhering to rigid industrial norms.

You can use SMT solvers like z3-solver (PyPI: z3-solver) to determine bounding box positions:

> 1. **Variables:** Declare *Xi*​,*Yi*​ grid variables for each relay, fuse, and terminal.  
> 2. **Constraints:**  
   * *Y*Fuse​\<*Y*Relay​ (Fuses placed above Relays).  
   * *Y*Terminal​\=*Y*Max​ (Terminals anchored to bottom rail).  
   * *XB*​≥*XA*​\+Width*A*​\+MinSpacing (No overlap).  
> 3. **Solve:** Z3 computes exact grid coordinates in milliseconds per page.  
> 4. **Route:** Run an orthogonal A\* pathfinder on the resulting coordinate matrix to generate the wire SVGs.

### **3\. Industrial Control Cabinet Drawing Rules**

To ensure auto-generated cabinet drawings remain readable for technicians, enforce these rigid rules inside your layout pipeline:

| Component Type | Vertical Standard (*Y*\-Axis) | Horizontal Flow (*X*\-Axis) | Routing Constraint |
| :---- | :---- | :---- | :---- |
| **Power Rails** | Top (*L*1/*L*2/*L*3, \+24V) & Bottom (*N*, 0V) | Spans entire page width | Horizontal straight lines across columns. |
| **Protective Devices** | Upper third (below power rail) | Left to Right by circuit index | Wires feed straight down into control logic. |
| **Relays / Contactors** | Middle region | Left to Right (Coil → Contacts) | Coils drawn on control page; contacts cross-referenced. |
| **Terminal Blocks (*X*1,*X*2\)** | Bottom margin (*Y*≈*Y*max​−100px) | Sequential pin numbering (1,2,3…) | Wires leave downward toward field devices. |

### **Summary Recommendation**

> 1. **For PCB / SKiDL Visual Reviews:** Use a Python script to convert SKiDL netlists into schemdraw elements. It produces clean, vector-accurate SVGs that match standard schematic conventions.  
> 2. **For Multi-Page Cabinet Automation:** Implement a **Python Partitioning Layer** that splits the main network graph into distinct page sub-graphs based on functional blocks and power trees. Pass each single-page sub-graph into an orthogonal solver (either elkpy or a custom Z3 constraint grid builder) to emit pure SVGs per page.

---

*User prompt: The algorithm or layout engine do not have to be fast, as the layout is computed locally and seldom. Schemdraw is not the correct engine, as that has different standard symbols, and are not created for electrical cabinet circuits, but for electronics and smaller circuits*

Response: Because performance is not a bottleneck and you need strict adherence to industrial electrical standards (IEC 60617 / NFPA 79 for control cabinets, DIN rails, ladder logic, terminal strips, and coil/contact cross-referencing), using standard graph engines (like Graphviz or basic force-directed layouts) will continually fight your layout requirements.

Traditional graph engines try to minimize overall line lengths, whereas industrial cabinet schematics require **column-based grid alignment, ladder structure, and fixed functional rows**.

Since you want to stay strictly in Python and use your own code-defined SVG symbol library, building a specialized **Deterministic Grid-Constraint Layout Engine** in pure Python is the cleanest and most maintainable path.

### **Architectural Design for a Custom Cabinet Layout Engine**

Instead of relying on a generic graph solver, build a three-stage layout pipeline in Python designed specifically around cabinet drafting rules:

`[ System Netlist / SKiDL ]`  
           `│`  
           `▼`  
`Stage 1: Multi-Page Partitioner (Power Trees & Function Blocks)`  
           `│`  
           `▼`  
`Stage 2: Column & Ladder Grid Solver (Row/Column Allocation)`  
           `│`  
           `▼`  
`Stage 3: Orthogonal A* Channel Router (Wire Routing)`  
           `│`  
           `▼`  
      `[ SVG Output ]`

### **Stage 1: Multi-Page Partitioning Logic**

For multi-page industrial drawings, split components across pages based on structural roles rather than purely topological graph clusters:

> 1. **Power & Distribution Pages (Pages 1–N):**  
   * Filter for components connected to main line voltage (*L*1,*L*2,*L*3,*N*,*PE*) or primary DC buses (+24V,0V).  
   * Group main breakers, fuses, power supplies, transformer primaries, and motor starters.  
> 2. **Control & Logic Pages:**  
   * Group PLC I/O cards, relay coils, sensors, and pushbuttons by machine function or physical location.  
> 3. **Terminal Strip Pages (Terminal Diagrams):**  
   * Generate dedicated terminal location sheets (*X*1,*X*2…) showing incoming field wiring vs. internal cabinet wiring.  
> 4. **Cross-Reference Engine:**  
   * When a net breaks across pages (e.g., contactor coil *K*1 on Page 3 operating contact *K*1 on Page 1), replace the net segment with an **Off-Page Marker** storing source/destination page and grid matrix coordinates (e.g., /2.D4).

### **Stage 2: Structural Column & Ladder Grid Placement**

Cabinet drawings rely on a rigid coordinate matrix (typically columns 0–9 across the *X*\-axis and rows A–H along the *Y*\-axis). You can write a deterministic Python class to assign components to this grid.

`class CabinetGrid:`  
    `def __init__(self, columns=10, max_height=800):`  
        `# Y-Axis Fixed Zones (Industrial Standard Hierarchy)`  
        `self.Y_POWER_RAIL_TOP = 50    # L1 / +24V`  
        `self.Y_PROTECTION = 150       # Fuses, Breakers`  
        `self.Y_CONTROL = 350          # Switches, Relay Contacts, PLC Outputs`  
        `self.Y_LOADS = 550            # Relay Coils, Solenoids, Indicator Lights`  
        `self.Y_POWER_RAIL_BOTTOM = 700 # N / 0V / GND`  
        `self.Y_TERMINALS = 750        # Terminal Strip (X1)`

    `def assign_column(self, rung_components):`  
        `"""`  
        `Places a vertical circuit rung (e.g. Fuse -> Button -> Relay Coil)`  
        `into a dedicated vertical column on the page grid.`  
        `"""`  
        `# Calculate X coordinate based on column index`  
        `# Place components at their designated Y-zone based on type`  
        `pass`

#### **Placement Rules to Enforce in Python:**

> * **Vertical Rungs:** Control circuits flow top-to-bottom. A single vertical line should handle: **Fuse → Emergency Stop → Control Switch → Contactor Coil → Ground Rail**.  
> * **Fixed Y-Zones:** Assign a fixed *Y*\-coordinate zone for every component class (Fuses at *Y*\=150, Switches at *Y*\=350, Coils at *Y*\=550). This produces clean horizontal alignment across all columns on a page.  
> * **Component Anchor Points:** Ensure all terminal/pin coordinates on your custom Python SVG symbols snap strictly to integer grid steps (e.g., 10mm or 20px).

### **Stage 3: Orthogonal Channel Routing (A\* Pathfinding)**

Once components are placed in rigid grid slots, route the connecting wires orthagonally without using diagonal lines or curves.

Because layout speed is not a priority, an *A Grid Pathfinder*\* with directional penalties will generate clean, readable routing:

`import heapq`

`def route_orthogonal_wire(grid_map, start_pin, end_pin):`  
    `"""`  
    `A* pathfinder modified with turn penalties for industrial wire routing.`  
    `"""`  
    `# Grid steps (e.g., 10px cells)`  
    `open_set = []`  
    `heapq.heappush(open_set, (0, start_pin, None)) # (cost, position, current_direction)`  
      
    `# Cost Rules:`  
    `# 1. Base step cost = 1`  
    `# 2. Direction change (turn) penalty = 15 (forces long straight wire runs)`  
    `# 3. Obstacle / Symbol bounding box penalty = Infinity`  
    `# 4. Wire crossing / overlap penalty = 5 (discourages overlapping parallel runs)`  
      
    `# Returns an ordered list of (x, y) waypoints for <polyline> SVG rendering`

### **Pure Python Technology Stack Summary**

| Task | Recommended Approach | Why it fits your requirements |
| :---- | :---- | :---- |
| **Data Model & Netlist** | **SKiDL / Native Python AST** | Keeps circuit definitions completely in Python. |
| **Symbol Rendering** | **Custom SVG Library (Existing)** | Retains exact control over symbol geometry, text labels, and pin locations. |
| **Page Partitioning** | **Rule-based Graph Splitter** | Splits power, logic, and terminal strips into separate pages automatically. |
| **Placement Engine** | **Deterministic Zone/Grid Allocator** | Forces components into strict cabinet columns and standard *Y*\-level rows. |
| **Wire Routing** | *A Pathfinder with Turn Penalties*\* | Generates clean orthogonal lines along designated routing channels. |

By building a deterministic grid and channel router rather than attempting a generic force-directed graph layout, your generated SVGs and PDFs will consistently match standard industrial cabinet drafting formats.

---

*User prompt: Does these algorithms, the pathfinder and grid allocator exist as implemented functions/libraries in python? Or are there clear definitions of them that an ai agent can easily implement? Or do i have to write it from scratch and tweak it myself to get it right?*

Response: Ready-made Python libraries that generate industrial control cabinet schematics out-of-the-box **do not exist**.

Generic layout packages (like NetworkX, Graphviz, or grid managers) treat nodes as abstract points and try to shrink wire length. They have no concept of IEC 60617/NFPA 79 conventions—such as horizontal power rails, top-to-bottom control rungs, fixed component heights, or DIN terminal strips at the bottom.

The core underlying mathematical building blocks exist in standard Python libraries, and the rules governing control cabinet drafting are deterministic. An AI agent can implement a custom layout engine for your codebase with clear, well-structured prompts.

### **The State of Python Libraries vs. Custom Build**

| Component | Off-the-shelf Python Library? | Can an AI Agent Generate It? | What to Use / How to Ask |
| :---- | :---- | :---- | :---- |
| **Grid Allocator / Matrix Manager** | **No** (GUI layout tools like Tkinter grid don't apply to schematics) | **Yes, easily** | Prompt for a **Zone-based Coordinate Mapper** that maps components to matrix coordinates based on component type. |
| *Orthogonal A Wire Router*\* | **Partial** (pathfinding on PyPI exists, but lacks turn penalties) | **Yes, trivial** | Write an *A grid router with turn penalties and crossing costs*\* in under 100 lines of pure Python. |
| **Multi-Page Partitioner** | **No** | **Yes, via rule trees** | Write simple graph traversal logic that groups components by power supply domains or signal chains. |

### **How to Prompt an AI Agent to Implement Each Stage**

Break the implementation into three isolated, highly specified modules for an AI coding agent (like Claude Code, Copilot, or GPT-4o).

#### **1\. The Grid Allocator (Structural Placement)**

Industrial schematics follow a row/column ladder structure. Instead of asking the AI for a "schematic layout algorithm," instruct it to build a **Slot-Based Coordinate Allocator**.

> * **Prompt instructions for AI:**  
  "Create a Python class CabinetGridAllocator. It takes a page budget of *X*\-columns (0 to *N*) and fixed *Y*\-zones:  
  * *Y*\=50: Top Power Rail (+24V/*L*1\)  
  * *Y*\=150: Protection Devices (Fuses, Breakers)  
  * *Y*\=350: Switches / Contacts / Inputs  
  * *Y*\=550: Actuators / Relay Coils / Outputs  
  * *Y*\=700: Bottom Power Rail (0V/*N*)  
  * *Y*\=800: Terminal Strip (*X*1\) Write a method assign\_rung(column\_index, components) that places components in column *X* at their matching *Y*\-zone based on their type attribute, returning absolute (*x*,*y*) coordinates for the component anchors."

#### **2\. The Orthogonal A\* Pathfinder (Wire Routing)**

Standard A\* paths choose jagged zig-zag routes. To get clean schematics, the pathfinder must penalize direction changes (turns) heavily so wires stay straight.

> * **Prompt instructions for AI:**  
  "Write a pure Python class OrthogonalRouter that uses A\* pathfinding on a 2D grid map.  
  * Nodes are step coordinates (e.g. 10px grid).  
  * Component bounding boxes marked on the grid act as obstacles.  
  * Path movement cost: Straight step \= 1\.  
  * **Turn Penalty:** If current\_direction \!= previous\_direction, add a cost penalty of 20\.  
  * **Overlap Penalty:** If stepping on a grid cell that already contains a routed wire, add a cost penalty of 5 (disincentivizes wire bundling/crossings). Return a list of orthogonal (*x*,*y*) points formatted as an SVG \<polyline\>."

#### **3\. The Multi-Page Partitioner**

> * **Prompt instructions for AI:**  
  "Write a Python function partition\_netlist\_to\_pages(netlist):  
  1. Traverses the graph to find high-voltage or primary power sources, grouping them and their immediate protection devices into Page 1\.  
  2. Splits control loops into logical sub-graphs (max 8 vertical rungs per page).  
  3. For nets connecting across pages, truncate the wire at the page boundary and append an OffPageConnector node storing target page number and column label (e.g. /3.C2)."

### **Key Takeaway**

You do **not** need to invent complex topological math or do endless manual tweaking. The manual work is replaced by defining fixed **zone rules** (*Y*\-coordinates for fuses vs. coils) and setting a high **turn penalty** in an A\* router. Giving an AI agent these specific constraints will allow it to generate a clean, working layout engine in your native Python environment.

---

*User prompt: I have tried such strict rules, but with different circuits i often end up with some circuits looking fine, but others are much longer or weirdly spaced... The human touch of tweakin each circuit to fit nicely is still missing... Maybe the last year in ai agent cabability increase have made this easier to implement, as I haven't done much work on the layout since February 2026*

Response: The "weirdly spaced" and "artificially long" look happens because **algorithmic graph theory solves for spatial efficiency, while human drafting solves for semantic balance and visual weight**.

A rule set forces a tiny two-component sensor loop to consume the exact same column footprint as a dense motor starter circuit.

Recent advances in vision-language models (VLMs) and agentic workflows (e.g., Claude 3.5/3.7, GPT-4o) make adding a human-like aesthetic review loop much simpler. Rather than relying on an LLM to generate *X*,*Y* coordinates directly (which usually causes floating-point alignment errors), you can use a **VLM-in-the-Loop Refinement Pipeline**.

### **The VLM-in-the-Loop Pipeline Architecture**

Combine your deterministic Python script with a VLM acting as a senior electrical draftsman. The script generates an initial schematic, renders it as an image, and the VLM reviews it to provide specific layout adjustments.

`[Netlist / SKiDL]`   
       `│`  
       `▼`  
`1. Deterministic Python Draft (Zone Grid + A* Router)`  
       `│`  
       `▼`  
`2. Render Page to PNG Image`  
       `│`  
       `▼`  
`3. VLM Critic (Vision LLM evaluates visual weight & proportions)`  
       `│`  
       `├─► Returns JSON: {"adjustments": [{"symbol": "K1", "shift_x": -2, ...}]}`  
       `│`  
       `▼`  
`4. Python Engine Applies Adjustments & Re-renders PDF/SVG`

### **How to Implement the VLM Aesthetic Critic**

Because execution speed is not a constraint, running an agent loop once per page is straightforward.

#### **Step 1: Send the Image & Layout State to the VLM**

Supply the rendered PNG of the schematic page along with a JSON summary of where components were placed:

`{`  
  `"page": 2,`  
  `"components": [`  
    `{"id": "F1", "column": 1, "y_zone": "PROTECTION", "bbox": [100, 150, 140, 200]},`  
    `{"id": "K1", "column": 1, "y_zone": "COILS", "bbox": [100, 550, 140, 600]}`  
  `]`  
`}`

#### **Step 2: System Prompt for the Layout Critic**

Use a structured prompt that instructs the model to evaluate visual balance:

"You are a master electrical draftsman reviewing control cabinet schematics. Examine the attached PNG image and the component location JSON.

**Evaluate the following aesthetic defects:**

> 1. **Sparse/Stretched Columns:** Is a column horizontally spaced too far from its neighbor, creating empty white space?  
> 2. **Over-dense Regions:** Are component labels overlapping or sitting too close to adjacent wire channels?  
> 3. **Unnecessary Wire Bends:** Could shifting a component left or right by 1–2 grid units eliminate 90-degree wire jogs?

**Output strictly valid JSON** containing fine-tuning adjustments:

`{`  
  `"column_compression": [{"columns": [3, 4], "action": "merge_spacing", "delta_x_px": -40}],`  
  `"component_shifts": [{"id": "K1", "grid_shift_x": -1, "grid_shift_y": 0}]`  
`}`  
```` ```" ````

#### **Step 3: Apply the Nudges Deterministically**

Do not let the LLM rewrite the wire routing. Instead:

> 1. Apply the LLM's requested grid\_shift values to the components' grid slot assignments.  
> 2. Re-run your deterministic *A Orthogonal Router*\* on the adjusted positions.  
> 3. If the VLM approves the visual balance (or after a max of 2 refinement iterations), output the final SVG/PDF.

### **Why This Hybrid Approach Works**

| Pure Code Constraints | Pure LLM Generation | Hybrid VLM Agent Loop |
| :---- | :---- | :---- |
| Rigorous alignment, but looks rigid, stretched, or artificially spaced. | High visual intuition, but misaligned wires, wrong pin snaps, and hallucinated geometry. | **Deterministic precision for wires/pins \+ LLM visual intuition for spacing and proportions.** |

By keeping the VLM focused on **high-level spatial nudges** rather than raw SVG code generation, you get human-like schematic layouts without sacrificing electrical accuracy.

---

*User prompt: Can you recommend a vlm? More cabable of handling such visual reviews than standard coding agents like Claude opus?*

Response: Evaluating visual layout, grid spacing, and line density requires **spatial perception, bounding-box grounding, and geometric reasoning**—skills that standard coding LLMs (even top-tier models like Claude Opus 4 or Sonnet 3.7) often lack. Coding agents excel at text and syntax, but treat images as low-resolution feature maps, struggling with fine-grained spatial coordinates or subtle visual balance.

To build a reliable VLM-in-the-Loop review system, you need models optimized for **DocVQA, visual grounding, sub-pixel OCR, and spatial UI/layout evaluation**.

### **Top VLMs for Visual Layout & Schematic Review**

#### **1\. Gemini 3.5 Flash / Gemini 2.5 Pro (Google) — *Best API Option***

> * **Why it wins:** Google’s vision models lead in high-resolution spatial reasoning and visual grounding. They natively support extremely high-resolution image inputs without downsampling them into unreadable blur, making them ideal for reading tiny text labels (e.g., relay pin tags or fuse values) alongside wire paths.  
> * **Best used for:** Detecting overlapping text, sparse column gaps, and checking whether wire channels look cluttered.

#### **2\. Qwen2.5-VL-72B / Qwen3-VL (Alibaba) — *Best Open-Weights / Self-Hosted Option***

> * **Why it wins:** Qwen’s vision models are specifically tuned for **Document VQA and bounding-box layout parsing**. They excel at returning structured JSON containing exact bounding boxes \[ymin, xmin, ymax, xmax\] for visual elements.  
> * **Best used for:** Local deployment if privacy or air-gapping is required. It directly outputs precise coordinate offsets for components that need shifting.

#### **3\. Florence-2 / SAM 3 (Microsoft / Meta) — *Best Specialized Vision Backends***

> * **Why it wins:** These are lightweight, vision-specific models rather than full LLMs. Florence-2 handles zero-shot object detection and spatial grounding, while SAM 3 handles segmenting dense regions.  
> * **Best used for:** A fast, deterministic pre-pass to detect text/wire collisions before passing the image to a larger LLM for layout feedback.

### **Prompting Strategy for Layout Nudging**

To prevent the VLM from making vague suggestions, instruct it to act as a **bounding-box auditor** that outputs structured JSON:

`LAYOUT_REVIEW_PROMPT = """`  
`You are an expert electrical draftsman auditing a control cabinet schematic PNG.`  
`Analyze the image for these three visual defects:`  
`1. SPARSITY: Two adjacent columns separated by more than 150px of empty space.`  
`2. CROWDING: Text labels overlapping or sitting within 5px of a wire.`  
`3. UNNECESSARY_JOGS: A wire that takes two 90-degree turns when shifting a component 1 grid slot left/right would make it straight.`

`Return ONLY a JSON list of nudges using grid-slot deltas (-2 to +2):`  
`{`  
  `"nudges": [`  
    `{"component_id": "K1", "grid_shift_x": -1, "reason": "Align coil vertically with switch S2 to eliminate wire jog"},`  
    `{"component_id": "F3", "grid_shift_x": 1, "reason": "Clear label overlap with left rail"}`  
  `]`  
`}`  
`"""`

### **Recommended Pipeline Architecture**

Instead of replacing your existing agent setup, split the pipeline into two focused roles:

> 1. **Claude Code / Opus:** Handles the Python code generation, AST parsing of your netlist, and execution of the A\* router.  
> 2. **Gemini 3.5 Flash API or Qwen2.5-VL:** Acts as the dedicated vision evaluator that inspects the rendered PNG, returns the JSON nudge coordinates, and lets your Python script re-run the layout deterministically.

**Sources**

> 1. [The State of Multimodal AI: What VLMs Can Actually Do | 2026](https://www.codesota.com/guides/multimodal-ai)  
> 2. [Best Computer Vision Models in 2026: A Task-by-Task Guide](https://blog.roboflow.com/best-computer-vision-models/)

---

*User prompt: Can I run Qwen 2.5 vl on my hp laptop z book? Or will that be really slow?*

Response: **Yes, you can run Qwen 2.5 VL on your HP ZBook, but how fast it runs depends heavily on which model size you pick and whether your ZBook has a dedicated Nvidia Quadro/RTX graphics card.**

### **Hardware Breakdown: Dedicated GPU vs. CPU**

Most ZBook workstations come equipped with dedicated **Nvidia RTX/Quadro GPUs** (such as an RTX A2000, A3000, or RTX 3000/4000 Ada series) alongside 32 GB+ of system RAM:

> * **Scenario A: Running on a Dedicated Nvidia GPU (Fast)**  
  * If your model fully loads into your dedicated GPU's VRAM, execution will be fast (roughly 30–60 tokens/second).  
  * **Requirements:** The **Qwen 2.5 VL 7B (Q4 quantization)** requires roughly 5.5–6 GB of VRAM. If your ZBook GPU has 6 GB or 8 GB+ VRAM, the entire model will offload onto the GPU seamlessly.  
> * **Scenario B: Running on CPU / System RAM (Slow)**  
  * If your ZBook relies solely on Integrated Intel/AMD Graphics, or if your GPU has only 4 GB VRAM, the system will spill over into standard DDR4/DDR5 system RAM.  
  * System RAM bandwidth is significantly slower than VRAM, resulting in speeds around 2–6 tokens/second. It will be usable, but noticeably sluggish during long generation runs.

### **Expected Performance by Model Variant**

Qwen 2.5 VL comes in multiple sizes. You can choose the variant that best matches your workstation's hardware:

| Model Variant | Quantization | Required VRAM / RAM | Typical Speed (Dedicated GPU) | Typical Speed (CPU / Integrated) |
| :---- | :---- | :---- | :---- | :---- |
| **Qwen 2.5 VL 3B** | Q4\_K\_M | ∼3.5 GB | **Very Fast** (60+ tok/s) | **Usable** (8–12 tok/s) |
| **Qwen 2.5 VL 7B** | Q4\_K\_M | ∼6.0 GB | **Fast** (30–50 tok/s) | **Slow** (2–5 tok/s) |
| **Qwen 2.5 VL 72B** | Q4\_K\_M | ∼45.0 GB | *Exceeds laptop VRAM* | **Extremely Slow** (\<1 tok/s) |

### **How to Get the Best Speed**

> 1. **Use Ollama with GGUF Quantization:** Run the model quantized to 4-bit (Q4\_K\_M). It reduces memory consumption by ∼60% while maintaining visual accuracy.  
>    `# For laptops with 4GB-6GB VRAM GPUs:`  
>    `ollama run qwen2.5-vl:3b`

>    `# For laptops with 8GB+ VRAM GPUs:`  
>    `ollama run qwen2.5-vl:7b`

> 2. **Limit Image Resolution:** Vision-Language Models scale processing time relative to input image size. If you pass an ultra-high-resolution image or PDF page without downscaling, processing the initial prompt image (prefill phase) will take longer.

**Recommendation:** If your ZBook has an Nvidia GPU with **8 GB VRAM**, run the **7B (Q4)** model for optimal layout evaluation. If your GPU has **4 GB VRAM** or uses integrated graphics, use the **3B (Q4)** model to prevent system RAM offloading and keep speeds interactive.

**Sources**

> 1. [Qwen2.5 7B: Size, VRAM & Ollama Setup (2026) \- Local AI Master](https://localaimaster.com/models/qwen-2-5-7b)

---

*User prompt: What about doing the review on the svg directly? Are there engines that can give me results from an svg, like which pins match in x and y, Linea that are not straight, overlapping text on lines...*

Response: Analyzing the SVG document directly **is significantly cleaner, faster, and more reliable** than using a Vision-Language Model (VLM).

Because your software generates the SVG elements, you have direct access to exact vector geometry, text bounding boxes, and coordinates. Instead of having an AI guess spatial relations from pixels, you can run **pure 2D computational geometry checks in Python**.

There is no off-the-shelf "electrical SVG linter" engine, but you can build a **Geometric Rule Linter** in a few lines of Python using existing spatial libraries.

### **The Python Stack for SVG Layout Inspection**

To evaluate an SVG programmatically, parse the SVG vector geometries using three lightweight libraries:

> 1. **svgpathtools / svgpath2mpl:** Converts SVG \<path\>, \<line\>, and \<polyline\> elements into standard geometric paths.  
> 2. **shapely:** The industry-standard Python 2D spatial analysis library. It handles exact geometric intersections, distance checks, and containment queries.  
> 3. **fontTools or matplotlib:** Estimates text string bounding boxes based on font size and character length.

### **Key Linter Rules Implemented via Geometry**

#### **1\. Overlapping Text on Lines (Text-to-Wire Collision)**

Text elements (\<text\>) have an anchor point (*X*,*Y*), font size, and character length.

> * **How to detect:** Create a 2D bounding box Polygon in shapely for each text label. Convert wire \<polyline\> elements into LineString objects.  
> * **Check:** Run shapely.intersects(text\_box, wire\_line). If True, you have a collision.

#### **2\. Crooked / Non-Straight Wires**

Electrical cabinet schematics require purely orthogonal (horizontal or vertical) lines.

> * **How to detect:** Iterate over segment endpoints (*x*1​,*y*1​) to (*x*2​,*y*2​) of a \<polyline\>.  
> * **Check:**  
>   `is_horizontal = abs(y2 - y1) < 1e-3`  
>   `is_vertical = abs(x2 - x1) < 1e-3`

>   `if not (is_horizontal or is_vertical):`  
>       `# Report defect: Non-orthogonal wire segment!`

#### **3\. Unaligned Pins (Misaligned Terminals Across Components)**

To check if terminal pin *A* on component 1 aligns horizontally or vertically with terminal pin *B* on component 2:

> * **How to detect:** Extract terminal pin coordinates from your code-defined SVG symbols.  
> * **Check:**  
>   `# Check horizontal alignment within tolerance`  
>   `if abs(pinA.y - pinB.y) <= GRID_STEP:`  
>       `if pinA.y != pinB.y:`  
>           `# Report defect: Pins are slightly off-grid (jogged by few pixels)!`

#### **4\. Redundant Wire Bends (Unnecessary Jogs)**

If a wire takes a 3-segment "U-shape" or "Z-shape" path to connect two pins when a straight 1-segment line would reach it without obstacle collisions:

> * **How to detect:** Check if len(polyline.points) \> 2\. Cast a straight line between start\_pin and end\_pin.  
> * **Check:** If the straight line does not intersect any component bounding boxes, flag the wire for simplification.

### **How to Use SVG Direct Analysis in Your Workflow**

This approach fits neatly into an automated testing or optimization loop:

`[ Netlist / SKiDL ]`  
        `│`  
        `▼`  
`1. Deterministic Layout Script (Generates SVG)`  
        `│`  
        `▼`  
`2. SVG Geometry Linter (Shapely + Python)`  
        `│`  
        `├─► [ Pass ] ──► Final SVG / PDF Render`  
        `│`  
        `└─► [ Fail ] ──► Returns Precise Defect List:`  
                         `- "K1 label intersects wire Net3 at (140, 220)"`  
                         `- "F1.pin2 (x=102) misaligned with K1.pin1 (x=100)"`  
        `│`  
        `▼`  
`3. Deterministic Nudge Solver (Nudges components in grid units to clear defects)`

### **Advantage Over VLM Inspection**

> * **Speed:** Runs in milliseconds per page, compared to seconds or minutes for VLM API calls or local model inference.  
> * **Precision:** Deterministic to sub-pixel accuracy.  
> * **No Hallucinations:** Prevents false positives or missed overlaps that happen with pixel-based image reviews.

---


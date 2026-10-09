# The lore trail: how the player learns what happened

The intro shows one thing: Remand Salvager #4471's Program drop aircraft going down short of the
drop site. **Nothing tells the player what started the outbreak.** The cause (a Corvane Mining Co.
drill hole broke into the caves under the valley and let out the Bloom) is pieced together from
what they find: notes, journals, Cordon paperwork, the tethers of dead salvagers, signs. This doc
is the story's canon and a map of where each beat is found, so new notes stay consistent with it.

Read it before writing a note, sign, tether log, radio transcript or trader line.

## 1. The truth (author's canon, never stated whole in one early place)

* The **Corvane Mining Co.** works the **Corvane Deep Mine** and explores around it from
  **Field Station 2 (FS-2)**, its geology camp at the end of the exploration road (POI
  `corvane_field_lab`), and the **Larkspur exploration adit** (`corvane_larkspur_adit`).
* In **March of Year 1** (eighteen months before the player arrives), **hole BH-7**, a step-out
  drilled from the Deep Mine's **4 Level**, broke into an open void at **1,411 ft** in grey
  limestone. Warm air came up the rods smelling of bread; the core (boxes 211-214) came up
  threaded with white filaments that turn from light. Geologist **Ted Brask** logged it; driller's
  helper **Lars Engen** was on the rig.
* The company kept drilling into the void for six weeks (BH-8 to BH-10) to measure the find. It is
  not a pocket: it is a **cave system under the whole valley** holding **one very old mycelium**.
  On the surface its growing edge is **the Bloom**; **the Hollowed** are how it walks.
* In **April** the government's **Cordon Medical Authority** quietly took FS-2 (Directive 14) as a
  forward lab: **Dr. C. Marchetti** and her team, Biosafety Officer **I. Torvald**. It wrote the
  public story the same month: *a chemical release at the Corvane works* (the screening brief
  dated 14 April). The **Remand Program** was already its specimen-collection arm.
* Every seventh night the network contracts at once (**the Hum**); every host turns toward it.
  Its centre is a chamber under the ridges **north of the Deep Mine**, which the Program's survey
  party named **the Root** (DESIGN §10: the Root under the mountain, beyond Whitecap).
* FS-2 fell around **June** (a Hum, the containment suite breached from inside; Torvald sealed the
  vault with seven cores). The Deep Mine shut "for safety" in June and paid its crews to stay home.
* **July**: Corvane's **crew 3** (No. 4 Level) reach Dr. Anneliese Voss at the Tamsin Valley
  Clinic with a cough and white threads in the sputum. The company asks her to hush it up.
* **Sept 1**: **Order 14** closes Route 9 and every road off the mountain. Assembly points, buses
  that never come, checkpoints, holding sites. **Sept 9**: the first Hum felt valley-wide (lookout,
  clinic). September to November the valley falls.
* **Year 2**: the Program drops convicts to bring out cores and data. #2271 is taken by the Ashen
  in March; **#3907 (C. Pruitt, contract 77-B)** dies at FS-2's core shed; **#4471** (the player)
  arrives in the autumn, eighteen months after BH-7, on Program aircraft **Lift 3**: it crossed the
  firebreak at first light, lost an engine over shaking timber and went down short of Larch Hollow;
  #4471 walked the last mile to the drop site (the intro, DESIGN §1). The wreck burned out where
  it fell (`lift3_crash_site`); its two pilots, Capt. N. Whitlock and F/O J. Iredale, died in it.

Rules that follow from it:
* **The cover story is "a chemical spill/release at the Corvane works".** Civilians repeat it or
  doubt it; nobody early knows better.
* **Who knows what.** Townsfolk know only that miners got sick and the ground hums. Company staff
  know the drill hit something and are scared. The Cordon's paperwork knows the agent is a fungus
  from underground and that the index cases were underground workers, and hides it. Only FS-2, the
  Program's survey and the men on the rig know the bore opened it.
* **The Program knew early.** Its people took samples at Larkspur and its survey says "do not inform
  the company"; it wants the organism alive. Hint at it, never explain it.

## 2. The beats and where they are found

Tiers are the POI's tier. "Main" = the main map (only region D6 is built: the Pell's Crossing
framework plus D6's region features). "Random" = random worlds: wilderness POIs by chance per
region (`world_gen.json`), any authored building whose zoning fits a town lot (LotPicker), and the
forest encounters everywhere. The lab and the adit are `unique` and chance-placed (≈0.07-0.08 per
region), so **no beat may rest on one building**.

### Beat 1. Rumours (tier 1-2): something is wrong at the company; the ground hums

| Piece (note id) | Where | Tier | Worlds | What it gives |
|---|---|---|---|---|
| Letter from Anders (`wild_trapper_anders`) | Lindqvist's Trapline Cabin | 1 | main, random (most common wild POI) | FS-2 exists; Brask's core boxes nobody may touch; a car with no plates; "it hasn't had a spill" |
| Notebook Page, Things People Said (`enc_camp_rumours`) | abandoned-camp encounter | - | both | mine shut in June, crews paid to keep quiet; "chemicals don't make the ground hum" |
| Tally Under the Tarp (`enc_lift_tally`) | tarp-cache encounter | - | both | the Program's lost lifts (Lift 1 in the firebreak, Lift 2 never landed); "stay off Corvane property and don't ask why"; "if you came down on Lift 3" |
| Cedar Ridge Lookout log (`wild_lookout_log`) | Cedar Ridge Lookout | 1 | both | Hum bearings cross "up north under the ridges. Under it." |
| Unsent Letter (`okafor_letter`), Ife's Journal (`farm_ife_journal`) | Okafor farmhouse | 3 | both | the radio's spill story; "Papa says it's the mine. Tom says it's the government." |
| Tamsin Valley Courier (`road_courier`) | Cordon Gas & Garage | 2 | both | illness first seen among Corvane Deep Mine crews |
| Returns Book, Archive Tag (`t3_library_returns`, `t3_library_archive`) | Pell County Library (pool) | 2 | random towns | every book on the county's caves is out; the Cordon boxed the Corvane mine maps |
| Letter to June (`w5_hatchery_manager_letter`) | Silver Run Hatchery | 2 | random | the Bloom "comes down the creek from somewhere up past the falls" |
| Lift Manifest, Kneeboard Card, Seat-Back (`lift3_manifest`, `lift3_kneeboard`, `lift3_seatback`) | The Lift 3 Wreck (`lift3_crash_site`) | 1 | main (~0.7 km east of the drop); random once World places it | the player's own lift: one salvager for three seats (#4466 dead in holding, #4479 cut the tether), "only one we're paid for"; over the firebreak at 0541, "treeline moving, no wind, ground moving", number two lost; earlier salvagers' numbers scratched on a seat (#2271, #3318, #3907): "nobody says how many come back empty" |

### Beat 2. Company paper and sick miners (tier 2-3)

| Piece | Where | Tier | Worlds | What it gives |
|---|---|---|---|---|
| Dr. Voss's Patient Log (`road_voss_log`) | Tamsin Valley Clinic | 2 | main, random towns | July: O. Okafor and crew 3, white threads in the sputum |
| Letter from Corvane Mining Co. (`road_corvane_letter`) | Tamsin Valley Clinic | 2 | main, random towns | the company hushes up "Crew 3 (No. 4 Level) and Exploration Drilling"; "where are the drillers?" |
| Notice to the Water Department (`town4_waterworks_discharge`) | Water Works (pool) | 2 | random towns | exploration drilling met a warm inflow at depth; white floc that moves from light |
| Remains Tag (`enc_recovery_tag`) | Cordon recovery encounter | - | both | a CORVANE 4 LVL check token; the Program wants dead miners listed by name |
| Ranger Station Logbook (`ranger_log`) | Pell ranger station | 3 | main (pool in random) | "Tell them it started at the mine." |
| Shift Boss's Log, Breakthrough Report (`corvane_shift_log`, `corvane_breakthrough`) | Larkspur Adit | 3 | main, random (unique) | a second breach: a stope holes into a warm void with luminous white growth; "they knew it was there" |

### Beat 3. Cordon paperwork (tier 3)

| Piece | Where | Tier | Worlds | What it gives |
|---|---|---|---|---|
| Screening Team Brief (`town2_screening_brief`) | Consolidated School, isolation cellar | 3 | main, random towns | dated 14 April; the spill line is official; banned words FUNGUS, SPORE, MINE, CAVE, BLOOM; Corvane underground workers named to FS-2 |
| Medical Officer's Briefing (`w3_qc_briefing`) | Cordon Quarantine Camp | 3 | random | the agent is a fungus of subterranean origin; index cases underground workers of one employer; the origin blacked out ("see FS-2 file"); the seven-day event |
| Chain of Custody, CFL-044/3 (`w4_plane_custody`) | Cordon Transport Wreck | 3 | random | a drill-core segment, BH-7 at 1,412 ft, released by Torvald from the FS-2 vault |
| Field Results, Water Section (`w5_hatchery_cordon_results`) | Silver Run Hatchery | 2 | random | the agent rides surface water |
| Order 14 and its kin (`out_camp_notice`, `w4_depot_closure_order`, `w4_relay_schedule`...) | campground, depot, relay hut... | 1-3 | both | the Cordon's shape: roads closed Sept 1, no second convoy |

### Beat 4. The science (tier 3-5)

| Piece | Where | Tier | Worlds | What it gives |
|---|---|---|---|---|
| Survey 3, Cross-Section Notes (`corvane_survey_section`), Survey Memo (`corvane_program_seal`) | Larkspur Adit, lowest level | 3 | main, random (unique) | BH-7's void and the adit's are one cave system; one organism; it thickens north toward the Root; the Hum's source; "no drill log before BH-7 shows growth" |
| Painted Hide (`ashen_highcamp_hide`) | Ashen Highcamp | 3 | random | the Ashen's picture: a rig on the mountain, a line down into a hollow of white roots, the roots up the line into a man; walkers every seven dots |
| Sample Log, Station Log, Directive 14, Biosafety Log (`lab_*`) | Corvane Field Lab | 5 | random (unique) | cultures pulse with the Hum; Brask's own tissue; the lab's fall |

### Beat 5. The truth (tier 4-5, deep places)

| Piece | Where | Tier | Worlds | What it gives |
|---|---|---|---|---|
| Statement, Folded in a Glove (`wild_mill_engen`) | Larch Hollow Sawmill, filing room | 4 | main, random | an eyewitness: BH-7 at 1,411 ft, the warm air, the threads on the core, three more holes into open cave under the whole valley |
| Core Log, BH-7 (`lab_core_log`) | Corvane Field Lab, core shed | 5 | random | Brask's log of the void: warm air, filaments on every fracture face; "the threads moved away from the lamp" |
| Interim Report No. 3 (`lab_marchetti_report`) | Corvane Field Lab, cold room | 5 | random | the whole answer: sealed cave, BH-7 opened it in March, six more weeks of drilling with the Authority's knowledge, one mycelium, the Hum, "they want it alive" |
| Tether, Salvager #3907 (`lab_tether_3907`) | Corvane Field Lab, core shed | 5 | random | the Program sends convicts for exactly this |

On the main map a curious player gets the whole story from the trapline cabin, the clinic, the
school, the farm, the ranger station, the adit and the sawmill. In a random world the truth sits in
four chance places (the sawmill, the adit, the highcamp, the lab), with the Cordon paperwork (school,
quarantine camp, plane wreck) and the encounters pointing at it from many more.

### What early places must not say

The intro leaves the player with rumours, the guards' talk of the Hum, a Cordon notice ("hazard:
biological, unidentified") and one hint from the drop briefing: "Corvane Mining property is out of
bounds. Do not ask why." Early notes may build on that hint but must not answer it.

Tier 1-2 houses and shops, the drop site, the first directives (chapters 1-2), the Field Manual,
the loading tips and the trader's and Ezra's lines never name the cause. They may say: people got
sick, miners first; the radio says a spill; the ground hums; the Cordon closed the roads. Checked
for this pass: the Field Manual's TIPS (`game/src/ui/field_manual.gd`), the directives, Ezra's
barks, Waystation 9's contract briefings and the HUD tip say nothing of the cause.

## 3. Names, numbers and dates to keep straight

* **Calendar**: BH-7 in March Y1; the screening brief 14 April; FS-2 lost about June; Voss's first
  crew-3 patient Jul 12; Order 14 (roads) **Sept 1**; the Courier's "Route 9 closed" issue
  Thursday Sept 2; first valley-wide Hum **Sept 9**. Pell's Crossing notes run Aug 31 - Sep 7 (the
  postmaster, Lou's radio log, the pharmacy, the hardware store, the garage, the motel). Farm,
  chapel, trestle in Oct; the trapper in Nov. Undated "Day N" logs count from the Cordon.
* **The Hum comes every seventh night.** Never write "the third Hum" months in.
* **Orders**: Order 14 = road closure (Cordon Authority). Order 22 = firearms. Directive 14 (Cordon
  Medical Authority) = FS-2's requisition. Field Directive 7 = the clinic.
* **Depths**: the void at 1,411 ft; the core and specimens at 1,412 ft. BH-7 to BH-10.
* **Salvager numbers**: #2271 (the Ashen pit), #3318 (the highcamp blind), #3907 (C. Pruitt, FS-2,
  contract 77-B), #4471 (the player). Lift 3's manifest struck two more: #4466 (R. Dace, died in
  holding the night before) and #4479 (E. Sowa, cut the tether, absent at muster); neither came in.
  Tag/ticket numbers 4471 elsewhere are deliberate echoes.
* **Lift 3**: a Program lift out of Waystation 9, crew Capt. N. Whitlock and F/O J. Iredale; wheels
  up 0530, over the firebreak 0541, number two engine lost 0542-0543, Control's last call 0544.
* **People who recur**: Ted Brask (geologist, BH-7), Lars Engen (driller's helper), Anders
  Lindqvist (FS-2 manager) and his brother Arvid (the trapper), Dr. C. Marchetti, BSO I. Torvald,
  Dr. Anneliese Voss (clinic), Lt. M. Okonkwo (school, Cordon Medical) and Lt. A. Okonkwo (hatchery,
  water section) are two people. Ezra Vane is the living companion: no dead or turned character is
  called Ezra. Common valley surnames (Lindqvist, Pruitt/Pruett, Haldane, Okafor) repeat on purpose
  across families; officers and named witnesses do not.
* **Random-world notes name no town** (tests check Pell, Merrow, Larch, Hollowmere, Tamsin,
  Bracken). Corvane, FS-2 and BH-7 are the company's and may be named anywhere.

## 4. Adding a piece

1. Decide its beat and keep it there: a tier 1-2 piece may hint, a tier 3 piece may document, only
   tier 4-5 or deep places may explain.
2. Put any beat a player needs in two or more buildings, at least one on the main map and at least
   one common in random worlds (or an encounter).
3. Match the calendar and names above; add new recurring names here.
4. Add the note def (`game/data/notes/`), its item `note_<id>` (reuse a generic note model such as
   `items/note_pharmacy_ledger` for typed paper, `items/note_okafor_letter` for a letter,
   `items/farm_note_page` for a page), and **append** the slot to the POI's `notes`
   (docs/POI_AUTHORING.md: never reorder). Then `validate`.
5. Update the tables here.

Open questions (TECH_DEBT TD-371..374): the main map has no field lab yet (DESIGN puts it on
Lantern Island, D4; the POI is a hillside station at the end of the exploration road), random
worlds guarantee none of the truth places, and main-map buildings that random worlds also place
carry notes naming Pell's Crossing, the Tamsin road or Larch Hollow.

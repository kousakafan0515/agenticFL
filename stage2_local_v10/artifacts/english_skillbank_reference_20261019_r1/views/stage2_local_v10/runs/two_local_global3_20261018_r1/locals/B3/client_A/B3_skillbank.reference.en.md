# English reference: B3_skillbank.json

Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.

## Planner — General

### G_001: Search visible surfaces first and broaden across plausible locations

**Principle:** When a target object's location is unknown, locate it before manipulation by checking open, directly observable surfaces and common holding places first, such as tables, countertops, desks, dressers, shelves, beds, sofas, and chairs. Only then open closed containers such as drawers, cabinets, fridges, and microwaves. Treat the search as a broad multi-location search rather than assuming one named receptacle contains the object; if an early location is empty, broaden to other plausible unchecked locations.

**When To Apply:** When the target object's location is unknown at the start, or when the first checked location does not contain it.

### G_002: Failure Lesson

**Description:** Failed searches often repeat the same empty surfaces or failed take attempts, or conclude the object is unavailable before all plausible open surfaces and relevant containers have been checked. A search should maintain a checked-location list and move to a new unchecked plausible location after a failed take.

**Why It Happens:** The search may be treated as an unconstrained sequence without bookkeeping, so empty locations are revisited and some plausible locations are never examined.

**How To Avoid:** Record each checked location and its result. After a failed take or empty look, mark that location checked and move to another plausible unchecked location. Do not revisit confirmed empty surfaces unless the environment state changed. Open closed receptacles before treating them as searched and prioritize locations by object type. Search likely containers and surfaces; if the object remains absent after relevant locations are exhausted, report failure rather than continuing indefinitely.

### G_003: Open closed containers before taking or placing, and verify destination openability

**Principle:** When a closed drawer, cabinet, safe, fridge, microwave, or similar container may hold the target or is the placement destination, navigate to it and open it before attempting to take from it or put into it. Closed containers cannot be inspected or used directly. Before placing, confirm the destination is already open or can be opened; if opening returns no change, treat it as non-openable and choose a valid open destination or surface. For non-openable fixtures, use only a go-then-put sequence.

**When To Apply:** When the target may be inside a closed container, or when the placement destination is closed or its openability is uncertain.

### G_004: Navigate to the object and destination before take or put; proceed directly after acquisition

**Principle:** A take action succeeds only when the actor is at the receptacle where the object is present, and a put action succeeds only when the actor is at the destination. Locate and acquire the target object before traveling to the target container. Once the target is held, go directly to the specified destination and place it without unnecessary intermediate steps; if a put fails, verify current location and navigate to the destination before retrying.

**When To Apply:** When retrieving an object whose location is not current, when moving a held object to a destination, or after a failed put.

### G_005: Use exact action forms, identifiers, and matching object types

**Principle:** Use the environment's supported action forms: go to a location, take an object from a receptacle, put an object in or on a receptacle, and open a container before accessing it. Refer to exact object and receptacle identifiers from observations, and track the specific instance taken so later actions use the same one. Do not use examine or open on non-container surfaces; open only applies to openable containers. Before taking or transforming, confirm the object name matches the goal, because similar but different objects may not satisfy it. If many containers have been checked without success, reassess visible surfaces and the target description rather than continuing blind exhaustive checks.

**When To Apply:** Throughout object search, retrieval, and placement, especially when forming commands or when an action seems unsupported or ambiguous.

### G_006: Failure Lesson

**Description:** When an action such as go to, open, take, put, use, or clean returns 'Nothing happens', do not repeat the same command. Failed attempts can come from being at the wrong location, using an inexact or invalid identifier, targeting a closed or non-openable receptacle, or trying an inaccessible location. After a failed placement, verify current location and navigate to the destination before retrying. Treat an unreachable navigation target as unavailable and switch to another candidate; treat an already-open container as open and continue rather than reopening it. Repeated no-change results are evidence that the current approach is exhausted.

**Why It Happens:** The same invalid action may be retried without updating the inferred state, and a failed task segment may be reissued identically instead of changing the search location, object description, or strategy.

**How To Avoid:** After a no-change observation, re-check location, inventory, exact identifiers, and object or container state. Change at least one relevant condition: move to a different reachable location, open a closed container, use the specific instance id, or switch to another strategy. After one or two identical failures, stop retrying. If a task segment fails or returns without meeting its condition, do not repeat it unchanged; broaden the search or change the approach. Before declaring blocked, ensure every plausible closed container was actually opened and inspected, not merely approached, and avoid revisiting surfaces already confirmed empty.

### G_007: Use an acquire-then-operate sequence with explicit completion conditions

**Principle:** For tasks that require an object to be found and then manipulated, cleaned, heated, cooled, examined, or placed, split the task into an acquisition phase and an operation phase. The acquisition phase ends only when the target object is actually held, not merely seen or when a container is opened. The operation phase ends only when the environment observation confirms the required final state, such as the object being at the destination, cleaned, heated, or cooled. Begin placement only after acquisition is confirmed by holding the target object.

**When To Apply:** When a goal requires an object to be acquired before it is used, transformed, or placed, and the object is not already held.

### G_008: Failure Lesson

**Description:** Do not declare completion or stop based on an attempted action alone. After critical actions such as take, put, clean, heat, or cool, inspect the observation for the goal predicate. Declare success only when the observation confirms the required final state; declare failure only when the observation shows an invalid or blocked action, an unreachable object, or exhaustion of plausible locations. If the placement observation already confirms the goal, treat it as terminal and do not run a redundant verification step.

**Why It Happens:** Plans may assume an action succeeded without checking feedback, or may declare failure after a successful action sequence, or may add an unnecessary verification step after success, causing loops.

**How To Avoid:** After each critical action, compare the observation with the expected state. If the action failed, retry only after adjusting the approach; if it succeeded, stop issuing extra actions. Treat a confirming placement, cleaning, heating, or cooling observation as the terminal success condition. Do not declare completion before the final placement is confirmed; after confirmation, stop and do not send empty or inventory-only actions.

## Planner — Simple pick-and-place

### T1_001: Simple pick-and-place procedure

**Principle:** For simple pick-and-place goals, decompose the task into two ordered subtasks: first locate and take the target object, then move to the specified destination and put the object down.

**When To Apply:** When the goal is to move a single object to a specified destination and no additional state change such as cleaning, heating, cooling, or lighting is required.

## Planner — Examine with desk lamp

### T2_001: Desklamp observation: locate the target object and the desklamp, and use the desklamp at the furniture where the desklamp is located

**Principle:** First confirm the locations of the target object and the desklamp; the desklamp is usually fixed on a furniture surface. If the desklamp has already been observed on a surface such as a desk, side table, or dresser, go directly to that furniture and do not continue searching unrelated containers or blindly opening drawers. If the target object is not at the desklamp, first obtain and carry the target object to that furniture; if the target object is already at the desklamp, directly try to use the desklamp, and if the interaction is not accepted, ensure the target object is in hand and retry. After arriving, execute the command use desklamp <id> with the instance ID to trigger the observation; do not use bare names or compound syntax, and do not treat the desklamp as a carryable object or navigation point. Successfully turning on the desklamp is the termination condition; do not append use/look afterward.

**When To Apply:** When the task requires examine/look at something with/under the desklamp, and an interactable desklamp exists in the environment.

### T2_002: Failure Lesson

**Description:** Multiple failed trajectories show that take desklamp, go to desklamp, or repeatedly going to the desklamp/desk usually returns Nothing happens, wastes steps, and may block subsequent observation. The desklamp is an interaction point fixed on furniture, not a carryable object or navigable location.

**Why It Happens:** The environment models the desklamp as a fixed light source or fixed device; only the furniture where it is located can be a navigation target, and the desklamp itself cannot be the target of take or go to.

**How To Avoid:** Do not try to take, move, or navigate to the desklamp. First reach the furniture that holds the desklamp (desk, sidetable, dresser, coffeetable, etc.), and after arriving, directly execute the command use desklamp <id> with the ID; if already at the desklamp, do not repeatedly go to the same location.

### T2_003: Failure Lesson

**Description:** In failed trajectories, examine X with desklamp, examine the target object, examine desklamp, bare-name use desklamp, use desklamp on X, and use X on desklamp often return There's nothing special about X or Nothing happens, and cannot replace the observation condition. Merely placing the target object on the desk or desklamp without triggering the desklamp interaction also makes the task appear complete while the environment goal is not achieved.

**Why It Happens:** The environment does not support using the desklamp as a tool parameter for examine, nor does it support bare names or compound syntax; the placement action itself does not trigger the observation success condition.

**How To Avoid:** After locating the target object and bringing it to the furniture where the desklamp is located, use the observed numbered lamp instance to execute use desklamp <id>. Do not use examine X with desklamp or compound use syntax; if invalid syntax has been tried, verify the desklamp instance name and retry, rather than repeatedly examining the target object or desklamp.

### T2_004: Failure Lesson

**Description:** If use desklamp returns Nothing happens, it usually means you are not currently at the desklamp location or the interaction conditions are not met; repeating the same use/examine/look command at the same location will not change the state and may form a loop or trigger protection. After one or two consecutive failures, stop repeating.

**Why It Happens:** Using the desklamp requires being at the same furniture where the desklamp is located, and incorrect syntax or location will not produce a state change; mistaking an empty observation for a retryable signal will repeat ineffective actions.

**How To Avoid:** After a failure, first check whether the target object and desklamp are at the current furniture; if necessary, move to the observed desklamp furniture, switch to use desklamp <id> with the ID, or first obtain or keep the target object and retry; if there is still no change, switch to searching other locations or declare that it cannot be completed, and do not repeat the same command.

### T2_005: Desklamp observation search strategy: prioritize open surfaces and systematically check containers

**Principle:** When searching for the target object or desklamp, prioritize open surfaces related to the desklamp, such as desk, sidetable, nightstand, bed, armchair, coffee table, shelves, etc.; once the desklamp is observed, go directly to the furniture where it is located and use the desklamp if needed; do not continue traversing many drawers. If the reasonable open surfaces do not contain the target object, then systematically search by container type (drawer/cabinet), and after finding it return to the desklamp. Avoid repeatedly look/examine at the same location; when there is no new information, move to other furniture or containers. 'under the desklamp' does not guarantee that the target object or desklamp is necessarily at the assumed location, so when the assumed location is not visible, search other surfaces and containers.

**When To Apply:** When searching for the target object or desklamp in a desklamp observation task, or when you have reached the assumed desklamp location but the target object or desklamp is not there and repeated observations yield no new information.

## Planner — Clean then place

### T3_001: Clean-then-place ordered workflow with clean-state check

**Principle:** For goals requiring a clean object to be placed, execute distinct stages: locate and acquire the target object; bring it to a compatible cleaning fixture, preferring a sinkbasin; clean it; confirm from the observation that cleaning succeeded; then go to the destination, open it if closed, and place the object. Do not place before cleaning, and do not treat the clean step as done unless the observation confirms it. If cleaning has not succeeded, return to the cleaning stage before attempting placement.

**When To Apply:** When the goal is to put a clean object in or on a specified receptacle and the object is not already clean.

### T3_002: Failure Lesson

**Description:** A clean action can return no effect when the object is not held or the current location is not a valid cleaning fixture. Cleaning is reliably supported at a sinkbasin; alternative fixtures such as bathtubbasin or fridge should not be assumed equivalent. Repeated identical attempts waste steps.

**Why It Happens:** The environment validates that the object is held and that cleaning occurs at a compatible fixture; some fixtures or objects do not support cleaning.

**How To Avoid:** Hold the target object, navigate to a sinkbasin, then clean. If no effect, verify the held object and current location; try a different sinkbasin or confirm the object is cleanable. Treat bathtubbasin as unverified and switch to sinkbasin if it fails; do not loop on an invalid fixture.

### T3_003: Failure Lesson

**Description:** Certain objects such as towels or cloth may not support the clean action at a sinkbasin; repeated clean attempts fail. Prefer objects that are typically cleanable, and if a clean attempt fails, consider that the chosen object may be unsuitable.

**Why It Happens:** Not every object type supports cleaning, or the selected object may not be the task's intended cleanable item.

**How To Avoid:** Before committing, select a likely cleanable candidate. If clean returns no effect after confirming the fixture and held object, try another candidate object or report the object as not cleanable rather than repeating the same action.

### T3_004: Failure Lesson

**Description:** Placement can fail when the destination container is closed, has no available space, or is not a valid receptacle; for example, some fixtures such as toilets or coffeemachines may reject placement. An open action may also return no effect if the container is already open or not openable.

**Why It Happens:** Containers may require opening or have capacity limits; some fixtures are not valid placement targets. Repeating put or open without changing conditions may waste steps.

**How To Avoid:** Before placing, open a closed destination; if open returns no effect, do not retry it—proceed or reassess. Check for space or availability when possible. If the destination is invalid or put repeatedly has no effect, seek an alternative valid destination or report blocked rather than looping.

### T3_005: Failure Lesson

**Description:** Goals name a specific object type. Similar alternatives, such as mug for cup, pan for pot, or butterknife for knife, should not be silently substituted. A close synonym may be considered only if the exact object is unavailable and the environment or observation explicitly treats it as equivalent or the goal permits it; otherwise continue searching or report the mismatch.

**Why It Happens:** Generalizing categories can cause taking the wrong item and failing the task; conversely, exact-name matching may miss an accepted synonym, so equivalence must be confirmed rather than assumed.

**How To Avoid:** First search for the exact named type. If not found, do not swap in a different type by default; only use a confirmed equivalent. If the destination already contains a similar object, still acquire, clean, and place the correct target rather than swapping.

### T3_006: Failure Lesson

**Description:** Searching for the target object should prioritize plausible locations and avoid opening every remaining container indefinitely. If the object is not found after checking a reasonable set of likely locations, reassess or report blocked rather than continuing a step-consuming loop.

**Why It Happens:** Item locations follow some regularities, but unusual placement or impossible tasks can occur; unbounded search wastes steps and can cause timeout or failure.

**How To Avoid:** Prioritize likely locations by object type: food-related items in fridge; dishes or utensils in countertop, cabinet, or drawer; cleaning supplies near sinkbasin, countertop, or shelf. After a few likely locations fail, consider unusual placement or impossibility, then reassess or report blocked rather than exhaustively opening all containers.

## Planner — Heat then place

### T4_001: End-to-end heat-then-place sequence

**Principle:** For a heat-then-place goal: locate and take the target object, go to the microwave, open it if closed, perform the heating operation using an observation-confirmed method, keep track of the same object instance, then go to the final destination, open it if needed, put the object there, and confirm placement. Treat heating as an intermediate milestone; the task is complete only after the object is placed at the destination. If the object is already held after acquisition, proceed to the heating stage rather than restarting unnecessarily.

**When To Apply:** Any task requiring an object to be heated and then placed at a specified destination.

### T4_002: Microwave heating with observation-driven holding/placement recovery

**Principle:** Open the microwave before taking from or using it, and keep it open until heating is confirmed. Use the explicit heat action form heat <object> with microwave <id> rather than generic use <object> or use microwave. Observations conflict on the required heating state: some successful runs heated the object while holding it, while others succeeded by placing the object in an open microwave and then heating. Treat the holding/placement requirement as observation-dependent. If heating while holding returns 'Nothing happens', place the object in the open microwave and retry. If heating with the object inside returns 'Nothing happens', take it out, ensure the microwave is open, and retry while holding it. Do not repeat an identical failing heat command without changing the object’s position or holding state.

**When To Apply:** When the target object must be heated with a microwave, especially if the first heat attempt fails or the object is inside the microwave.

### T4_003: Failure Lesson

**Description:** A heat command can fail or return 'Nothing happens', and treating an unconfirmed attempt as success can lead to moving and placing a cold object. Do not infer heating success from merely holding or placing the object.

**Why It Happens:** Heating may not change state unless the object’s position and the microwave state are suitable, and success is not guaranteed just because a command was issued.

**How To Avoid:** Proceed only after an explicit heating-success observation, such as a message that the object was heated, or another reliable confirmation that it is hot. If heating is not confirmed, repeat a valid heating attempt after correcting the object’s position or holding state, then verify again before moving it.

### T4_004: Failure Lesson

**Description:** After microwave heating returns 'Nothing happens', switching to stoveburners, toasters, or other appliances without evidence can also fail or be blocked. Assumption-based substitution adds failed steps rather than recovering the task.

**Why It Happens:** Some appliances may not support heating the target object, some surfaces may be occupied, and support for a given object or appliance is not guaranteed merely because an alternative exists.

**How To Avoid:** Correct the microwave interaction first: check that it is open, adjust whether the object is held or placed inside, and retry without repeating the identical failing command. Use another appliance only when current observations explicitly show that it supports heating this object and is available; otherwise do not treat stoveburner or toaster as a blind fallback.

### T4_005: Systematic search and continue after misses

**Principle:** When the target object is not in the first searched location, continue systematically checking other plausible containers and surfaces such as cabinets, drawers, countertops, dining table, fridge, sink basin, coffee machine, and stoveburners. Prioritize visible surfaces and high-probability containers by object type before opening every cabinet in sequence, and track checked locations to avoid redundant loops. Do not declare the task blocked or the object unavailable merely because the first location is empty.

**When To Apply:** During the acquisition phase of a heat-and-place task when the target object is not immediately visible or is absent from the first checked location.

### T4_006: Failure Lesson

**Description:** When heating succeeds while the object is held, the object remains in inventory. Attempting afterward to take it from the microwave can return 'Nothing happens' because the direct heat action did not put it there.

**Why It Happens:** The heating action confirmed while holding the object does not necessarily move the object into the microwave, so there is nothing to take out afterward.

**How To Avoid:** After a successful heat action performed while holding the object, verify by inventory or held-object state that it is still held, then proceed toward the destination. Do not issue a take-from-microwave action unless the object was actually placed inside.

### T4_007: Failure Lesson

**Description:** Inserting an extra countertop or other intermediate placement between heating and the final destination adds unnecessary actions and can cause tracking or placement failures.

**Why It Happens:** The task may be over-decomposed so that an intermediate placement is introduced even though the goal only requires moving the heated object to its final destination.

**How To Avoid:** After heating, take or keep the object and move directly to the final destination, then place it there. Add an intermediate placement only if the environment explicitly requires it.

## Planner — Cool then place

### T5_001: Cooling workflow with confirmed cool state before placement

**Principle:** Inputs differ on whether cooling requires placing the object in the fridge and taking it out or issuing an explicit cool action while holding it at an open fridge. Use environment feedback as authority: perform or verify cooling explicitly, and do not treat mere containment or brief placement as confirmed cooling. A reliable sequence is: acquire the exact target; go to the fridge; open it; if an explicit cool action is available, issue it while holding the object, otherwise use the available cooling interaction and wait for a cooled-state confirmation; then go to the destination; open it if closed; put the object there; confirm placement. Do not add a take-from-fridge step when cooling was done while holding, and do not immediately re-take an object already held; check inventory before re-taking.

**When To Apply:** When the goal requires an object to be cooled and then placed at a specified destination.

### T5_002: Failure Lesson

**Description:** An object found in the fridge, or briefly placed into it, is not guaranteed to be in the required cooled state. Cooling should be performed or verified explicitly before the object is taken to the destination.

**Why It Happens:** The agent may conflate storage location or containment with temperature state, or may assume that a fridge round-trip is sufficient cooling. The environment may only change temperature through an explicit cool interaction.

**How To Avoid:** Do not immediately retrieve and place an object after putting it into the fridge. While holding the target at an open fridge, use the environment's cool interaction and wait for a confirmation. If no cooled-state confirmation occurs, do not assume success.

### T5_003: Bounded systematic search and early feasibility reassessment

**Principle:** Check a few high-probability locations first, including the fridge, countertops, dining table, cabinets, drawers, and shelves. Open containers as needed and track visited locations to avoid redundant loops. If the target is not found after a reasonable broad search, reassess the goal or whether the object may be absent rather than continuing through every unrelated receptacle. Do not repeat an identical broad search after all obvious receptacles have been exhausted; report or escalate early when feasibility is doubtful.

**When To Apply:** When the target object is not immediately visible or is missing from its expected location, and many storage receptacles exist.

### T5_004: Failure Lesson

**Description:** Omitting the cooling phase and placing the object directly, or stopping after opening the fridge or cooling the object without final placement, leaves the goal incomplete. The task requires both a cooled object and placement at the required destination.

**Why It Happens:** The goal may be misread as a simple placement task, or the cooling step may be treated as the whole mission. Premature handoff after a partial step also causes failure.

**How To Avoid:** Treat cooling and final placement as separate checkpoints. Include an explicit cooling step before placement when the goal requires a cool object, and after cooling continue to the destination and place the object. Do not declare success or hand off until both the cooled state and destination placement have been confirmed.

## Planner — Place two objects

### T6_001: Sequential two-item placement with per-item confirmation

**Principle:** Treat a two-item placement goal as two search-and-place cycles. Locate and take one target object, navigate to the destination, open the destination if it is closed, place the object, and confirm the placement before starting the second cycle. Track how many items are placed and which object was already placed; never take an already-placed object again. If both instances are visible on the same surface or receptacle, place the first then return to that same location for the second. If the final destination is temporarily unavailable, only use a safe recoverable holding location when necessary and move both objects to the final destination afterward.

**When To Apply:** When the goal requires placing two instances of the same object type at one target location and only one object can be carried at a time.

### T6_002: Systematic search across receptacle types and visible surfaces

**Principle:** When target objects are not immediately visible, search broadly instead of checking only one receptacle type. Inspect visible surfaces such as counters, tables, shelves, sofas, dressers, and similar open surfaces first, then check closed containers such as cabinets and drawers, opening them before inspecting or taking from inside. Continue across multiple location types until the required number of instances is found or a checked-location record shows no remaining unchecked likely locations. Do not conclude the task is blocked prematurely, and do not accept a similar-named substitute for the exact target object type.

**When To Apply:** When one or both target objects are not visible and must be located in the environment.

### T6_003: Failure Lesson

**Description:** Attempts to take a second object, or sometimes to move to another location, while already holding an object can return a no-op. This blocks progress in two-item placement if the held object is not released first.

**Why It Happens:** The environment commonly allows carrying only one object at a time, so take or movement actions may be rejected while inventory is occupied.

**How To Avoid:** Before taking the second object or moving to search elsewhere, put the held object into the final destination or into a safe recoverable temporary location. Confirm the hands are empty, then continue.

### T6_004: Failure Lesson

**Description:** A put action can produce no effect if it is issued before reaching the destination receptacle, or it can fail without the failure being noticed. Continuing to search for the second item after an unconfirmed first placement can leave the goal unsatisfied.

**Why It Happens:** Placement requires being at the target container and a successful put must be verified from the observation; otherwise the first item may still be held or not placed.

**How To Avoid:** Navigate to the destination before placing. After each put, inspect the observation to confirm success. If the put did not succeed, move to the target if needed and retry before starting the next search or placement cycle. Track that the first item was already placed and drive directly to the second acquisition and final put.

### T6_005: Failure Lesson

**Description:** Attempting to put an object into, or take an object from, a closed cabinet, drawer, or similar container may produce no effect.

**Why It Happens:** The environment requires the container to be open before its contents can be accessed or modified.

**How To Avoid:** Open the container first with the appropriate open action. If it is already open, proceed; after opening, verify access before taking or placing.

### T6_006: Failure Lesson

**Description:** Using an examine-style action on objects or locations is not supported and returns no useful information.

**Why It Happens:** The available interaction set is limited to navigation, taking, putting, opening, and inventory-style operations; examining is not an effective substitute.

**How To Avoid:** Inspect a location by navigating to the receptacle and observing its contents. Pick up visible target objects with a take action from that receptacle.

### T6_007: Failure Lesson

**Description:** Placing an object into a non-target or unsuitable container such as a garbage can can make retrieval impossible or cause the overall two-item placement to fail.

**Why It Happens:** Some containers may not accept objects cleanly, may change object state, or may not allow reliable retrieval; temporary storage is only safe if the object can be taken back.

**How To Avoid:** Prefer placing the first object directly into the final destination. If temporary holding is unavoidable, choose an open, stable, recoverable surface or container and avoid garbage cans or other likely irreversible containers.

### T6_008: Failure Lesson

**Description:** After several containers have been opened and no target found, repeatedly revisiting locations already confirmed empty can exhaust the action budget and cause failure.

**Why It Happens:** Searching without tracking checked locations leads to redundant actions, while unchecked opened containers or visible surfaces may still contain the target.

**How To Avoid:** Maintain a mental or explicit list of checked locations. Prioritize unchecked opened containers and visible surfaces; take a target directly if it is visible. Avoid revisiting a location already confirmed to have no target unless new evidence suggests otherwise.

### T6_009: Failure Lesson

**Description:** Repeatedly declaring a subtask complete without executing the required next action can trigger a loop guard and terminate the episode before the two items are placed.

**Why It Happens:** The current state may be misread as satisfying the completion condition even though the actual goal or subgoal is unfinished, causing repeated signals instead of progress.

**How To Avoid:** Signal completion only after the corresponding subgoal is actually achieved, such as an object being taken or placed. After signaling, continue with the necessary next action and avoid repeating the same completion signal without new progress.

## Executor — General

### G_001: Search visible surfaces first and broaden across plausible locations

**Principle:** When a target object's location is unknown, locate it before manipulation by checking open, directly observable surfaces and common holding places first, such as tables, countertops, desks, dressers, shelves, beds, sofas, and chairs. Only then open closed containers such as drawers, cabinets, fridges, and microwaves. Treat the search as a broad multi-location search rather than assuming one named receptacle contains the object; if an early location is empty, broaden to other plausible unchecked locations.

**When To Apply:** When the target object's location is unknown at the start, or when the first checked location does not contain it.

### G_002: Failure Lesson

**Description:** Failed searches often repeat the same empty surfaces or failed take attempts, or conclude the object is unavailable before all plausible open surfaces and relevant containers have been checked. A search should maintain a checked-location list and move to a new unchecked plausible location after a failed take.

**Why It Happens:** The search may be treated as an unconstrained sequence without bookkeeping, so empty locations are revisited and some plausible locations are never examined.

**How To Avoid:** Record each checked location and its result. After a failed take or empty look, mark that location checked and move to another plausible unchecked location. Do not revisit confirmed empty surfaces unless the environment state changed. Open closed receptacles before treating them as searched and prioritize locations by object type. Search likely containers and surfaces; if the object remains absent after relevant locations are exhausted, report failure rather than continuing indefinitely.

### G_003: Open closed containers before taking or placing, and verify destination openability

**Principle:** When a closed drawer, cabinet, safe, fridge, microwave, or similar container may hold the target or is the placement destination, navigate to it and open it before attempting to take from it or put into it. Closed containers cannot be inspected or used directly. Before placing, confirm the destination is already open or can be opened; if opening returns no change, treat it as non-openable and choose a valid open destination or surface. For non-openable fixtures, use only a go-then-put sequence.

**When To Apply:** When the target may be inside a closed container, or when the placement destination is closed or its openability is uncertain.

### G_004: Navigate to the object and destination before take or put; proceed directly after acquisition

**Principle:** A take action succeeds only when the actor is at the receptacle where the object is present, and a put action succeeds only when the actor is at the destination. Locate and acquire the target object before traveling to the target container. Once the target is held, go directly to the specified destination and place it without unnecessary intermediate steps; if a put fails, verify current location and navigate to the destination before retrying.

**When To Apply:** When retrieving an object whose location is not current, when moving a held object to a destination, or after a failed put.

### G_005: Use exact action forms, identifiers, and matching object types

**Principle:** Use the environment's supported action forms: go to a location, take an object from a receptacle, put an object in or on a receptacle, and open a container before accessing it. Refer to exact numbered object and receptacle identifiers from observations, and track the specific instance taken so later actions use the same one. Do not use examine or open on non-container surfaces; open only applies to openable containers. Before taking or transforming, confirm the object name matches the goal, because similar but different objects may not satisfy it. If many containers have been checked without success, reassess visible surfaces and the target description rather than continuing blind exhaustive checks.

**When To Apply:** Throughout object search, retrieval, and placement, especially when forming commands or when an action seems unsupported or ambiguous.

### G_006: Failure Lesson

**Description:** When an action such as go to, open, take, put, use, or clean returns 'Nothing happens', do not repeat the same command. Failed attempts can come from being at the wrong location, using an inexact or invalid identifier, targeting a closed or non-openable receptacle, or trying an inaccessible location. After a failed placement, verify current location and navigate to the destination before retrying. Treat an unreachable navigation target as unavailable and switch to another candidate; treat an already-open container as open and continue rather than reopening it. Repeated no-change results are evidence that the current approach is exhausted.

**Why It Happens:** The same invalid action may be retried without updating the inferred state, and a failed task segment may be reissued identically instead of changing the search location, object description, or strategy.

**How To Avoid:** After a no-change observation, re-check location, inventory, exact identifiers, and object or container state. Change at least one relevant condition: move to a different reachable location, open a closed container, use the specific instance id, or switch to another strategy. After one or two identical failures, stop retrying. If a task segment fails or returns without meeting its condition, do not repeat it unchanged; broaden the search or change the approach. Before declaring blocked, ensure every plausible closed container was actually opened and inspected, not merely approached, and avoid revisiting surfaces already confirmed empty.

### G_007: Use an acquire-then-operate sequence with explicit completion conditions

**Principle:** For tasks that require an object to be found and then manipulated, cleaned, heated, cooled, examined, or placed, split the task into an acquisition phase and an operation phase. The acquisition phase ends only when the target object is actually held, not merely seen or when a container is opened. The operation phase ends only when the environment observation confirms the required final state, such as the object being at the destination, cleaned, heated, or cooled. Begin placement only after acquisition is confirmed by holding the target object.

**When To Apply:** When a goal requires an object to be acquired before it is used, transformed, or placed, and the object is not already held.

### G_008: Failure Lesson

**Description:** Do not declare completion or stop based on an attempted action alone. After critical actions such as take, put, clean, heat, or cool, inspect the observation for the goal predicate. Declare success only when the observation confirms the required final state; declare failure only when the observation shows an invalid or blocked action, an unreachable object, or exhaustion of plausible locations. If the placement observation already confirms the goal, treat it as terminal and do not run a redundant verification step.

**Why It Happens:** Plans may assume an action succeeded without checking feedback, or may declare failure after a successful action sequence, or may add an unnecessary verification step after success, causing loops.

**How To Avoid:** After each critical action, compare the observation with the expected state. If the action failed, retry only after adjusting the approach; if it succeeded, stop issuing extra actions. Treat a confirming placement, cleaning, heating, or cooling observation as the terminal success condition. Do not declare completion before the final placement is confirmed; after confirmation, stop and do not send empty or inventory-only actions.

## Executor — Simple pick-and-place

### T1_001: Simple pick-and-place procedure

**Principle:** For simple pick-and-place goals, decompose the task into two ordered subtasks: first locate and take the target object, then move to the specified destination and put the object down.

**When To Apply:** When the goal is to move a single object to a specified destination and no additional state change such as cleaning, heating, cooling, or lighting is required.

## Executor — Examine with desk lamp

### T2_001: Desklamp observation: locate the target object and the desklamp, and use the desklamp at the furniture where the desklamp is located

**Principle:** First confirm the locations of the target object and desklamp; the desklamp is usually fixed on a furniture surface. If the desklamp has already been observed on a surface such as a desktop, side table, or dresser, go directly to that furniture; do not continue searching unrelated containers. When the target object is not at the desklamp, first obtain the target object and carry it to that furniture; when the target object is already at the desklamp, you can directly try to use the desklamp; if the interaction is not accepted, ensure the target object is in hand and retry. After arriving, execute the command use desklamp <id> with the instance number to trigger observation; do not use a bare name or compound syntax, and do not treat the desklamp as a carryable object or navigation point.

**When To Apply:** When the task requires examine/look at something with/under the desklamp, and an interactable desklamp exists in the environment.

### T2_002: Failure Lesson

**Description:** Multiple failed trajectories show that take desklamp, go to desklamp, or repeatedly going to the desklamp/desk usually returns Nothing happens, wastes steps, and may block subsequent observation. The desklamp is an interaction point fixed on furniture, not a carryable object or navigable location.

**Why It Happens:** The environment models the desklamp as a fixed light source or fixed device; only the furniture where it is located can be a navigation target, and the desklamp itself cannot be the target of take or go to.

**How To Avoid:** Do not try to take, move, or navigate to the desklamp. First reach the furniture that holds the desklamp (desk, sidetable, dresser, coffeetable, etc.), and after arriving, directly execute the command use desklamp <id> with the ID; if already at the desklamp, do not repeatedly go to the same location.

### T2_003: Failure Lesson

**Description:** In failed trajectories, examine X with desklamp, examine the target object, examine desklamp, bare-name use desklamp, use desklamp on X, and use X on desklamp often return There's nothing special about X or Nothing happens, and cannot replace the observation condition. Merely placing the target object on the desk or desklamp without triggering the desklamp interaction also makes the task appear complete while the environment goal is not achieved.

**Why It Happens:** The environment does not support using the desklamp as a tool parameter for examine, nor does it support bare names or compound syntax; the placement action itself does not trigger the observation success condition.

**How To Avoid:** After locating the target object and bringing it to the furniture where the desklamp is located, use the observed numbered lamp instance to execute use desklamp <id>. Do not use examine X with desklamp or compound use syntax; if invalid syntax has been tried, verify the desklamp instance name and retry, rather than repeatedly examining the target object or desklamp.

### T2_004: Failure Lesson

**Description:** If use desklamp returns Nothing happens, it usually means you are not currently at the desklamp location or the interaction conditions are not met; repeating the same use/examine/look command at the same location will not change the state and may form a loop or trigger protection. After one or two consecutive failures, stop repeating.

**Why It Happens:** Using the desklamp requires being at the same furniture where the desklamp is located, and incorrect syntax or location will not produce a state change; mistaking an empty observation for a retryable signal will repeat ineffective actions.

**How To Avoid:** After a failure, first check whether the target object and desklamp are at the current furniture; if necessary, move to the observed desklamp furniture, switch to use desklamp <id> with the ID, or first obtain or keep the target object and retry; if there is still no change, switch to searching other locations or declare that it cannot be completed, and do not repeat the same command.

### T2_005: Desklamp observation search strategy: prioritize open surfaces and systematically check containers

**Principle:** When searching for the target object or desklamp, prioritize open surfaces related to the desklamp, such as desk, sidetable, nightstand, bed, etc.; once the desklamp is observed, go directly to the furniture where it is located and use the desklamp if needed; do not continue traversing many drawers. If the reasonable open surfaces do not contain the target object, then systematically search by container type (drawer/cabinet), and after finding it return to the desklamp. Avoid repeatedly look/examine at the same location; when there is no new information, move to other furniture or containers. 'under the desklamp' does not guarantee that the target object or desklamp is necessarily at the assumed location, so when the assumed location is not visible, search other surfaces and containers.

**When To Apply:** When searching for the target object or desklamp in a desklamp observation task, or when you have reached the assumed desklamp location but the target object or desklamp is not there and repeated observations yield no new information.

## Executor — Clean then place

### T3_001: Clean-then-place ordered workflow with clean-state check

**Principle:** For goals requiring a clean object to be placed, execute distinct stages: locate and acquire the target object; bring it to a compatible cleaning fixture, preferring a sinkbasin; clean it; confirm from the observation that cleaning succeeded; then go to the destination, open it if closed, and place the object. Do not place before cleaning, and do not treat the clean step as done unless the observation confirms it. If cleaning has not succeeded, return to the cleaning stage before attempting placement.

**When To Apply:** When the goal is to put a clean object in or on a specified receptacle and the object is not already clean.

### T3_002: Failure Lesson

**Description:** A clean action can return no effect when the object is not held or the current location is not a valid cleaning fixture. Cleaning is reliably supported at a sinkbasin; alternative fixtures such as bathtubbasin or fridge should not be assumed equivalent. Repeated identical attempts waste steps.

**Why It Happens:** The environment validates that the object is held and that cleaning occurs at a compatible fixture; some fixtures or objects do not support cleaning.

**How To Avoid:** Hold the target object, navigate to a sinkbasin, then clean. If no effect, verify the held object and current location; try a different sinkbasin or confirm the object is cleanable. Treat bathtubbasin as unverified and switch to sinkbasin if it fails; do not loop on an invalid fixture.

### T3_003: Failure Lesson

**Description:** Certain objects such as towels or cloth may not support the clean action at a sinkbasin; repeated clean attempts fail. Prefer objects that are typically cleanable, and if a clean attempt fails, consider that the chosen object may be unsuitable.

**Why It Happens:** Not every object type supports cleaning, or the selected object may not be the task's intended cleanable item.

**How To Avoid:** Before committing, select a likely cleanable candidate. If clean returns no effect after confirming the fixture and held object, try another candidate object or report the object as not cleanable rather than repeating the same action.

### T3_004: Failure Lesson

**Description:** Placement can fail when the destination container is closed, has no available space, or is not a valid receptacle; for example, some fixtures such as toilets or coffeemachines may reject placement. An open action may also return no effect if the container is already open or not openable.

**Why It Happens:** Containers may require opening or have capacity limits; some fixtures are not valid placement targets. Repeating put or open without changing conditions may waste steps.

**How To Avoid:** Before placing, open a closed destination; if open returns no effect, do not retry it—proceed or reassess. Check for space or availability when possible. If the destination is invalid or put repeatedly has no effect, seek an alternative valid destination or report blocked rather than looping.

### T3_005: Failure Lesson

**Description:** Goals name a specific object type. Similar alternatives, such as mug for cup, pan for pot, or butterknife for knife, should not be silently substituted. A close synonym may be considered only if the exact object is unavailable and the environment or observation explicitly treats it as equivalent or the goal permits it; otherwise continue searching or report the mismatch.

**Why It Happens:** Generalizing categories can cause taking the wrong item and failing the task; conversely, exact-name matching may miss an accepted synonym, so equivalence must be confirmed rather than assumed.

**How To Avoid:** First search for the exact named type. If not found, do not swap in a different type by default; only use a confirmed equivalent. If the destination already contains a similar object, still acquire, clean, and place the correct target rather than swapping.

### T3_006: Failure Lesson

**Description:** Searching for the target object should prioritize plausible locations and avoid opening every remaining container indefinitely. If the object is not found after checking a reasonable set of likely locations, reassess or report blocked rather than continuing a step-consuming loop.

**Why It Happens:** Item locations follow some regularities, but unusual placement or impossible tasks can occur; unbounded search wastes steps and can cause timeout or failure.

**How To Avoid:** Prioritize likely locations by object type: food-related items in fridge; dishes or utensils in countertop, cabinet, or drawer; cleaning supplies near sinkbasin, countertop, or shelf. After a few likely locations fail, consider unusual placement or impossibility, then reassess or report blocked rather than exhaustively opening all containers.

## Executor — Heat then place

### T4_001: End-to-end heat-then-place sequence

**Principle:** For a heat-then-place goal: locate and take the target object, go to the microwave, open it if closed, perform the heating operation using an observation-confirmed method, keep track of the same object instance, then go to the final destination, open it if needed, put the object there, and confirm placement. Treat heating as an intermediate milestone; the task is complete only after the object is placed at the destination. If the object is already held after acquisition, proceed to the heating stage rather than restarting unnecessarily.

**When To Apply:** Any task requiring an object to be heated and then placed at a specified destination.

### T4_002: Microwave heating with observation-driven holding/placement recovery

**Principle:** Open the microwave before taking from or using it. Observations conflict on the required heating state: some successful runs heated the object while holding it, while others succeeded by placing the object in an open microwave and then heating. Treat the holding/placement requirement as observation-dependent. If heating while holding returns 'Nothing happens', place the object in the open microwave and retry. If heating with the object inside returns 'Nothing happens', take it out, ensure the microwave is open, and retry while holding it. Do not repeat an identical failing heat command without changing the object’s position or holding state.

**When To Apply:** When the target object must be heated with a microwave, especially if the first heat attempt fails or the object is inside the microwave.

### T4_003: Failure Lesson

**Description:** A heat command can fail or return 'Nothing happens', and treating an unconfirmed attempt as success can lead to moving and placing a cold object. Do not infer heating success from merely holding or placing the object.

**Why It Happens:** Heating may not change state unless the object’s position and the microwave state are suitable, and success is not guaranteed just because a command was issued.

**How To Avoid:** Proceed only after an explicit heating-success observation, such as a message that the object was heated, or another reliable confirmation that it is hot. If heating is not confirmed, repeat a valid heating attempt after correcting the object’s position or holding state, then verify again before moving it.

### T4_004: Failure Lesson

**Description:** After microwave heating returns 'Nothing happens', switching to stoveburners, toasters, or other appliances without evidence can also fail or be blocked. Assumption-based substitution adds failed steps rather than recovering the task.

**Why It Happens:** Some appliances may not support heating the target object, some surfaces may be occupied, and support for a given object or appliance is not guaranteed merely because an alternative exists.

**How To Avoid:** Correct the microwave interaction first: check that it is open, adjust whether the object is held or placed inside, and retry without repeating the identical failing command. Use another appliance only when current observations explicitly show that it supports heating this object and is available; otherwise do not treat stoveburner or toaster as a blind fallback.

### T4_005: Systematic search and continue after misses

**Principle:** When the target object is not in the first searched location, continue systematically checking other plausible containers and surfaces such as cabinets, drawers, countertops, fridge, dining table, sink basin, coffee machine, and stoveburners. Do not declare the task blocked or the object unavailable merely because the first location is empty.

**When To Apply:** During the acquisition phase of a heat-and-place task when the target object is not immediately visible or is absent from the first checked location.

### T4_006: Failure Lesson

**Description:** When heating succeeds while the object is held, the object remains in inventory. Attempting afterward to take it from the microwave can return 'Nothing happens' because the direct heat action did not put it there.

**Why It Happens:** The heating action confirmed while holding the object does not necessarily move the object into the microwave, so there is nothing to take out afterward.

**How To Avoid:** After a successful heat action performed while holding the object, verify by inventory or held-object state that it is still held, then proceed toward the destination. Do not issue a take-from-microwave action unless the object was actually placed inside.

### T4_007: Failure Lesson

**Description:** Inserting an extra countertop or other intermediate placement between heating and the final destination adds unnecessary actions and can cause tracking or placement failures.

**Why It Happens:** The task may be over-decomposed so that an intermediate placement is introduced even though the goal only requires moving the heated object to its final destination.

**How To Avoid:** After heating, take or keep the object and move directly to the final destination, then place it there. Add an intermediate placement only if the environment explicitly requires it.

## Executor — Cool then place

### T5_001: Cooling workflow with confirmed cool state before placement

**Principle:** Inputs differ on whether cooling requires placing the object in the fridge and taking it out or issuing an explicit cool action while holding it at an open fridge. Use environment feedback as authority: perform or verify cooling explicitly, and do not treat mere containment or brief placement as confirmed cooling. A reliable sequence is: acquire the exact target; go to the fridge; open it; if an explicit cool action is available, issue it while holding the object, otherwise use the available cooling interaction and wait for a cooled-state confirmation; then go to the destination; open it if closed; put the object there; confirm placement. Do not immediately re-take an object already held; check inventory before re-taking.

**When To Apply:** When the goal requires an object to be cooled and then placed at a specified destination.

### T5_002: Failure Lesson

**Description:** An object found in the fridge, or briefly placed into it, is not guaranteed to be in the required cooled state. Cooling should be performed or verified explicitly before the object is taken to the destination.

**Why It Happens:** The agent may conflate storage location or containment with temperature state, or may assume that a fridge round-trip is sufficient cooling. The environment may only change temperature through an explicit cool interaction.

**How To Avoid:** Do not immediately retrieve and place an object after putting it into the fridge. While holding the target at an open fridge, use the environment's cool interaction and wait for a confirmation. If no cooled-state confirmation occurs, do not assume success.

### T5_003: Bounded systematic search and early feasibility reassessment

**Principle:** Check a few high-probability locations first, including the fridge, countertops, dining table, cabinets, drawers, and shelves. Open containers as needed and track visited locations to avoid redundant loops. If the target is not found after a reasonable broad search, reassess the goal or whether the object may be absent rather than continuing through every unrelated receptacle. Do not repeat an identical broad search after all obvious receptacles have been exhausted; report or escalate early when feasibility is doubtful.

**When To Apply:** When the target object is not immediately visible or is missing from its expected location, and many storage receptacles exist.

### T5_004: Failure Lesson

**Description:** Omitting the cooling phase and placing the object directly, or stopping after opening the fridge or cooling the object without final placement, leaves the goal incomplete. The task requires both a cooled object and placement at the required destination.

**Why It Happens:** The goal may be misread as a simple placement task, or the cooling step may be treated as the whole mission. Premature handoff after a partial step also causes failure.

**How To Avoid:** Treat cooling and final placement as separate checkpoints. Include an explicit cooling step before placement when the goal requires a cool object, and after cooling continue to the destination and place the object. Do not declare success or hand off until both the cooled state and destination placement have been confirmed.

## Executor — Place two objects

### T6_001: Sequential two-item placement with per-item confirmation

**Principle:** Treat a two-item placement goal as two search-and-place cycles. Locate and take one target object, navigate to the destination, open the destination if it is closed, place the object, and confirm the placement before starting the second cycle. Track how many items are placed and which object was already placed; never take an already-placed object again. If both instances are visible on the same surface or receptacle, place the first then return to that same location for the second. If the final destination is temporarily unavailable, only use a safe recoverable holding location when necessary and move both objects to the final destination afterward.

**When To Apply:** When the goal requires placing two instances of the same object type at one target location and only one object can be carried at a time.

### T6_002: Systematic search across receptacle types and visible surfaces

**Principle:** When target objects are not immediately visible, search broadly instead of checking only one receptacle type. Inspect visible surfaces such as counters, tables, shelves, sofas, and similar open surfaces first, then check closed containers such as cabinets and drawers, opening them before inspecting or taking from inside. Continue across multiple location types until the required number of instances is found or a checked-location record shows no remaining unchecked likely locations. Do not conclude the task is blocked prematurely.

**When To Apply:** When one or both target objects are not visible and must be located in the environment.

### T6_003: Failure Lesson

**Description:** Attempts to take a second object, or sometimes to move to another location, while already holding an object can return a no-op. This blocks progress in two-item placement if the held object is not released first.

**Why It Happens:** The environment commonly allows carrying only one object at a time, so take or movement actions may be rejected while inventory is occupied.

**How To Avoid:** Before taking the second object or moving to search elsewhere, put the held object into the final destination or into a safe recoverable temporary location. Confirm the hands are empty, then continue.

### T6_004: Failure Lesson

**Description:** A put action can produce no effect if it is issued before reaching the destination receptacle, or it can fail without the failure being noticed. Continuing to search for the second item after an unconfirmed first placement can leave the goal unsatisfied.

**Why It Happens:** Placement requires being at the target container and a successful put must be verified from the observation; otherwise the first item may still be held or not placed.

**How To Avoid:** Navigate to the destination before placing. After each put, inspect the observation to confirm success. If the put did not succeed, move to the target if needed and retry before starting the next search or placement cycle.

### T6_005: Failure Lesson

**Description:** Attempting to put an object into, or take an object from, a closed cabinet, drawer, or similar container may produce no effect.

**Why It Happens:** The environment requires the container to be open before its contents can be accessed or modified.

**How To Avoid:** Open the container first with the appropriate open action. If it is already open, proceed; after opening, verify access before taking or placing.

### T6_006: Failure Lesson

**Description:** Using an examine-style action on objects or locations is not supported and returns no useful information.

**Why It Happens:** The available interaction set is limited to navigation, taking, putting, opening, and inventory-style operations; examining is not an effective substitute.

**How To Avoid:** Inspect a location by navigating to the receptacle and observing its contents. Pick up visible target objects with a take action from that receptacle.

### T6_007: Failure Lesson

**Description:** Placing an object into a non-target or unsuitable container such as a garbage can can make retrieval impossible or cause the overall two-item placement to fail.

**Why It Happens:** Some containers may not accept objects cleanly, may change object state, or may not allow reliable retrieval; temporary storage is only safe if the object can be taken back.

**How To Avoid:** Prefer placing the first object directly into the final destination. If temporary holding is unavoidable, choose an open, stable, recoverable surface or container and avoid garbage cans or other likely irreversible containers.

### T6_008: Failure Lesson

**Description:** After several containers have been opened and no target found, repeatedly revisiting locations already confirmed empty can exhaust the action budget and cause failure.

**Why It Happens:** Searching without tracking checked locations leads to redundant actions, while unchecked opened containers or visible surfaces may still contain the target.

**How To Avoid:** Maintain a mental or explicit list of checked locations. Prioritize unchecked opened containers and visible surfaces; take a target directly if it is visible. Avoid revisiting a location already confirmed to have no target unless new evidence suggests otherwise.

### T6_009: Failure Lesson

**Description:** Repeatedly declaring a subtask complete without executing the required next action can trigger a loop guard and terminate the episode before the two items are placed.

**Why It Happens:** The current state may be misread as satisfying the completion condition even though the actual goal or subgoal is unfinished, causing repeated signals instead of progress.

**How To Avoid:** Signal completion only after the corresponding subgoal is actually achieved, such as an object being taken or placed. After signaling, continue with the necessary next action and avoid repeating the same completion signal without new progress.

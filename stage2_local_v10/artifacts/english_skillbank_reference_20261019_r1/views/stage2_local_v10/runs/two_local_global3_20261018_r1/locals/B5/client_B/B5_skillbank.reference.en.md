# English reference: B5_skillbank.json

Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.

## Executor — General

### G_001: Search observable surfaces first, then broaden to closed containers

**Principle:** When the target object's location is unknown, locate it before manipulation by checking open, directly observable surfaces and common holding places first: tables, countertops, desks, dressers, shelves, beds, sofas, chairs, and other plausible visible surfaces such as toilets or TV stands when they could hold the target. Only then open closed containers such as drawers, cabinets, fridges, microwaves, and similar receptacles. Treat search as a broad multi-location search rather than assuming one named receptacle contains the object. If an early location is empty, broaden to other plausible unchecked locations. If the target or a required fixture is already visible on a surface, go directly to that furniture instead of continuing unrelated container checks.

**When To Apply:** When the target object's location is unknown at the start, when the first checked location does not contain it, or when the target or a required fixture is already visible on a surface.

### G_002: Failure Lesson

**Description:** Failed searches often repeat the same empty surfaces or failed take attempts, revisit already-confirmed-empty locations, or conclude the object is unavailable before all plausible open surfaces and relevant containers have been checked. A search should maintain a checked-location list and move to a new unchecked plausible location after a failed take or empty look.

**Why It Happens:** Search may be treated as an unconstrained sequence without bookkeeping, so empty locations are revisited and some plausible locations are never examined; alternatively, failure may be declared after only a subset of locations is checked.

**How To Avoid:** Record each checked location and its result. After a failed take or empty look, mark that location checked and move to another plausible unchecked location. Do not revisit confirmed empty surfaces unless the environment state changed. Open closed receptacles before treating them as searched and prioritize locations by object type. If the object remains absent after relevant locations are exhausted, report failure rather than continuing indefinitely; but do not declare blocked while plausible unchecked locations remain.

### G_003: Open closed containers before taking or placing and verify destination openability

**Principle:** When a closed drawer, cabinet, safe, fridge, microwave, or similar container may hold the target or is the placement destination, navigate to it and open it before attempting to take from it or put into it. Closed containers cannot be inspected or used directly. Before placing, confirm the destination is already open or can be opened; if opening returns no change, treat it as non-openable and choose a valid open destination or surface. For non-openable fixtures, use only a go-then-put sequence.

**When To Apply:** When the target may be inside a closed container, or when the placement destination is closed or its openability is uncertain.

### G_004: Position at the object's receptacle before take and at the destination before put

**Principle:** A take action succeeds only when the actor is at the receptacle where the object is present, and a put action succeeds only when the actor is at the destination. When retrieving, first locate the object and position at its receptacle before taking. Once the target is held, travel directly to the specified destination and place it without unnecessary intermediate steps; if a put fails, verify current location and navigate to the destination before retrying.

**When To Apply:** When retrieving an object whose location is not current, when moving a held object to a destination, or after a failed put.

### G_005: Use supported action forms, exact identifiers, and matching object instances

**Principle:** Use only supported action forms: go to a location, take an object from a receptacle, put an object in or on a receptacle, open a container before accessing it, and use a fixture with its numbered instance when applicable. Refer to exact object and receptacle identifiers from observations, including instance numbers, and track the specific instance taken so later actions use the same one. Prefer navigating to locations, furniture, or receptacles rather than to a takeable object when the action form requires it. Do not use examine, look at, or open on non-container surfaces; open only applies to openable containers. Before taking or transforming, confirm the object name matches the goal, because similar types may not satisfy it. If many containers have been checked without success, reassess visible surfaces and the target description rather than continuing blind exhaustive checks.

**When To Apply:** Throughout object search, retrieval, and placement, especially when forming commands or when an action seems unsupported or ambiguous.

### G_006: Failure Lesson

**Description:** When an action such as go to, open, take, put, use, or clean returns no change, do not repeat the same command. Failed attempts can come from being at the wrong location, using an inexact or invalid identifier, targeting a closed or non-openable receptacle, or trying an inaccessible location. Treat an unreachable navigation target as unavailable and switch to another candidate; treat an already-open container as open and continue rather than reopening it. Repeated no-change results are evidence that the current approach is exhausted.

**Why It Happens:** The same invalid action may be retried without updating the inferred state, and a failed task segment may be reissued identically instead of changing the search location, object description, or strategy.

**How To Avoid:** After a no-change observation, re-check location, inventory, exact identifiers, and object or container state. Change at least one relevant condition: move to a different reachable location, open a closed container, use the specific instance id, or switch to another strategy. After one or two identical failures, stop retrying. If a task segment fails or returns without meeting its condition, do not repeat it unchanged; broaden the search or change the approach. Before declaring blocked, ensure every plausible closed container was actually opened and inspected, not merely approached, and avoid revisiting surfaces already confirmed empty.

### G_007: Separate acquisition from operation with observable completion conditions

**Principle:** For tasks that require an object to be found and then manipulated, cleaned, heated, cooled, examined, or placed, split the task into an acquisition phase and an operation phase. The acquisition phase ends only when the target object is actually held, not merely seen and not merely because a container was opened. The operation phase ends only when the environment observation confirms the required final state, such as the object being at the destination, cleaned, heated, or cooled. Begin placement only after acquisition is confirmed by holding the target object. If a subsequent phase or handoff follows, report acquisition only after the take observation confirms holding and note any remaining operation.

**When To Apply:** When a goal requires an object to be acquired before it is used, transformed, or placed, and the object is not already held.

### G_008: Failure Lesson

**Description:** Do not declare completion or stop based on an attempted action alone. After critical actions such as take, put, clean, heat, or cool, inspect the observation for the goal predicate. Declare success only when the observation confirms the required final state; declare failure only when the observation shows an invalid or blocked action, an unreachable object, or exhaustion of plausible locations. If the placement observation already confirms the goal, treat it as terminal and do not run a redundant verification step.

**Why It Happens:** An action may be assumed successful without checking feedback, failure may be declared after a successful sequence, or an unnecessary verification step may be added after success, causing loops.

**How To Avoid:** After each critical action, compare the observation with the expected state. If the action failed, retry only after adjusting the approach; if it succeeded, stop issuing extra actions. Treat a confirming placement, cleaning, heating, or cooling observation as the terminal success condition. Do not declare completion before the final placement is confirmed; after confirmation, stop and do not send empty or inventory-only actions.

## Executor — Simple pick-and-place

### T1_001: Simple pick-and-place procedure

**Principle:** For a simple pick-and-place goal, decompose the task into two ordered subtasks: first locate and take the target object, then move to the specified destination and put the object down.

**When To Apply:** When the goal is to move a single object to a specified destination and no additional state change such as cleaning, heating, cooling, or lighting is required.

## Executor — Examine with desk lamp

### T2_001: Desklamp observation: locate the target object and use the numbered desklamp at the furniture where the desklamp is located.

**Principle:** First confirm the locations of the target object and the desklamp. The desklamp is usually fixed on a furniture surface; after observing the desklamp, go directly to the furniture where it is located, do not continue searching unrelated containers or blindly open drawers, and do not treat the desklamp as a carryable item or navigation point. If the target object is not at the desklamp, first obtain it and carry it to that furniture; if the target object is already at the desklamp, first ensure the target object is in hand before interacting. Upon arrival, use the numbered instance with use desklamp <id> to trigger observation; do not use the bare name or compound syntax. Successfully turning on the desklamp is the termination condition; do not append use/look after it; if the target object has already been obtained at that furniture, do not go to the same location again.

**When To Apply:** When the task requires examine/look at something with/under the desklamp, and an interactable desklamp exists in the environment.

### T2_002: Failure Lesson

**Description:** Multiple failed trajectories show that take desklamp, go to desklamp, or repeatedly going to the desklamp/desktop usually returns Nothing happens, wasting steps and possibly blocking subsequent observation; the desklamp is an interaction point fixed on furniture, not a carryable item or navigable location.

**Why It Happens:** The environment models the desklamp as a fixed light source or fixed device; only the furniture where it is located can be a navigation target, and the desklamp itself cannot be the target of take or go to.

**How To Avoid:** Do not attempt to take, move, or navigate to the desklamp. First reach the furniture bearing the desklamp (desk, sidetable, dresser, coffeetable, etc.); once there, directly use the numbered use desklamp <id>; if already at the desklamp, do not go to the same location again.

### T2_003: Failure Lesson

**Description:** In failed trajectories, examine X with desklamp, examine the target object, examine desklamp, examine furniture (such as examine desk 1), bare-name use desklamp, use desklamp on X, use X on desklamp often return There's nothing special about X or Nothing happens, and cannot substitute for the observation condition. Merely placing the target object on the desk or desklamp without triggering the desklamp interaction also causes the task to appear complete while the environment goal is not achieved. The valid interaction form is to use the observed numbered lamp instance, for example use desklamp 1.

**Why It Happens:** The environment does not support using the desklamp as a tool argument to examine, nor does it support bare names or compound syntax; examining furniture also does not provide effective information; the placement action itself does not trigger the observation success condition.

**How To Avoid:** After locating the target object and bringing it to the furniture where the desklamp is located, use the observed numbered lamp instance to execute use desklamp <id>. Do not use examine X with desklamp, examine the target object/desklamp/furniture, or compound use syntax; if invalid syntax has been attempted, verify the desklamp instance name and retry, rather than repeatedly examining.

### T2_004: Failure Lesson

**Description:** If use desklamp returns Nothing happens, it usually means you are not currently at the desklamp's location, the current furniture observation does not include a desklamp, a bare name was used instead of a numbered instance, or the target object has not been obtained/the interaction conditions are not met; repeating the same use/examine/look command at the same location will not change the state and may form a loop or trigger protection. After one or two consecutive failures, stop repeating.

**Why It Happens:** Using the desklamp requires being at the same location as the furniture where the desklamp is located, and incorrect syntax (such as bare-name use desklamp), location, or not holding the target object will not produce a state change; mistaking an empty observation for a retry signal will repeat invalid actions.

**How To Avoid:** After a failure, first check whether the current furniture observation actually lists desklamp; if not, move to another furniture where a desklamp has been observed, rather than retrying the same use. If the desklamp is present, ensure the target object has been obtained or is held, then retry with the numbered use desklamp <id>; if there is still no change, search other locations or declare that it cannot be completed, and do not repeat the same command or fall back to examine.

### T2_005: Desklamp observation search strategy: prioritize open surfaces, then systematically check containers.

**Principle:** When searching for the target object or the desklamp, prioritize checking open surfaces related to the desklamp, such as desk, sidetable, nightstand, bed, dresser, sofa, coffeetable, armchair, shelf, etc.; once the desklamp is observed, go directly to the furniture where it is located and use the desklamp if needed, do not continue traversing many drawers or irrelevant containers. If the target object is not on reasonable open surfaces, then systematically search by container type (drawer/cabinet), and after finding it return to the desklamp. Avoid repeatedly look/examine the same location; when there is no new information, turn to other furniture or containers. 'under the desklamp' does not guarantee that the target object or the desklamp is necessarily at the assumed location, so when the assumed location is not visible, search other surfaces and containers.

**When To Apply:** When searching for the target object or desklamp in a desklamp observation task, or when you have reached the assumed desklamp location but the target object or desklamp is not there and repeated observations yield no new information.

## Executor — Clean then place

### T3_001: Clean-then-place sequence with verified cleaning

**Principle:** For a goal requiring a clean object to be placed, use separate stages: locate and acquire the named target; bring it to a compatible cleaning fixture, preferring a sinkbasin; clean it; verify from the observation that cleaning succeeded; then go to the destination, open it if closed, and place the object. Do not place before cleaning, and do not mark cleaning complete without confirming evidence. If cleaning did not succeed, return to the cleaning stage before placement. If transfer or handoff occurs after acquisition, record that cleaning is still required. Treat successful placement as the terminal condition.

**When To Apply:** When the goal is to put a clean object in or on a specified receptacle and the object is not already clean.

### T3_002: Failure Lesson

**Description:** A clean action may produce no effect when the target is not held, the current location is not a valid cleaning fixture, or the object is unsuitable. Cleaning is reliably supported at a sinkbasin in observations; alternatives such as bathtubbasin or fridge should not be assumed equivalent. Repeated identical clean attempts waste steps. Trying to take another object while still holding the failed object may also produce repeated no-ops.

**Why It Happens:** The environment appears to validate that the object is held and that cleaning occurs at a compatible fixture; not every fixture or object supports cleaning.

**How To Avoid:** Hold the target, navigate to a sinkbasin, then clean. If no effect, verify the held object and current location; try a different sinkbasin or confirm the object is cleanable. Treat bathtubbasin as unverified and switch to sinkbasin if it fails. After a failed clean, either try a different cleanable candidate after releasing the held object at a valid surface or report the object as not cleanable; do not loop on the same action.

### T3_003: Failure Lesson

**Description:** Some objects, such as towels or cloth, may not support the clean action at a sinkbasin; repeated clean attempts can keep failing. This may mean the object type is not cleanable or the selected object is not the intended cleanable item.

**Why It Happens:** Not every object type supports cleaning, and the chosen item may not be the task's intended cleanable target.

**How To Avoid:** Before committing to an object, choose a likely cleanable candidate. If clean returns no effect after confirming the fixture and that the object is held, stop repeating clean; try another candidate or report that the object is not cleanable.

### T3_004: Failure Lesson

**Description:** Placement can fail when the destination container is closed, has no available space, or is not a valid receptacle. Some fixtures, such as toilets or coffeemachines, may reject placement; repeated put/open/use on a coffeemachine can return no effect. An open action may also return no effect when the container is already open or not openable.

**Why It Happens:** Containers may require opening or have capacity limits, and some fixtures are not valid placement targets; repeating put or open without changing conditions can waste steps.

**How To Avoid:** Before placing, open a closed destination. If open returns no effect, do not retry it; treat it as already open or non-openable and proceed or reassess. Check space or availability when possible. If the destination is invalid or put repeatedly has no effect, seek an alternative valid destination or report blocked rather than looping.

### T3_005: Failure Lesson

**Description:** Goals specify an object type. Similar alternatives such as mug for cup, pan for pot, or butterknife for knife should not be silently substituted. A close synonym may be used only if the exact object is unavailable and the environment or observation explicitly treats it as equivalent, or the goal permits it; otherwise continue searching or report the mismatch. If the destination already contains a similar object, still acquire, clean, and place the correct target rather than swapping.

**Why It Happens:** Generalizing categories can cause taking the wrong item and failing the task, while exact-name matching may miss an accepted synonym; equivalence must be confirmed rather than assumed.

**How To Avoid:** Search first for the exact named type. If not found, do not swap in a different type by default; use only a confirmed equivalent. Confirm equivalence through explicit environmental or observational evidence or goal permission before substituting.

### T3_006: Failure Lesson

**Description:** Search should prioritize plausible locations but avoid opening every remaining container indefinitely or declaring blocked prematurely. Track checked locations and avoid revisiting confirmed-empty ones. After a reasonable set of likely locations has been checked—not merely one or two when many plausible ones remain—consider unusual placement or impossibility, then reassess or report blocked.

**Why It Happens:** Item locations may follow regularities, but unusual placement or impossible tasks can occur; unbounded search wastes steps and can cause timeout, while stopping too early can miss findable objects.

**How To Avoid:** Prioritize likely locations by object type: food-related items in fridge; dishes or utensils in countertop, cabinet, or drawer; cleaning supplies near sinkbasin, countertop, or shelf. Keep a record of checked locations. After several likely locations fail, consider unusual placement or impossibility and reassess or report blocked rather than exhaustively opening all containers or stopping after only a couple of empty locations.

## Executor — Heat then place

### T4_001: End-to-end process of heating first, then placing.

**Principle:** For a target that is heated first and then placed: locate and take the target object, go to the microwave, open it if closed, complete heating in a way confirmed feasible by observation, and continuously track the same object instance; then go to the final destination, open the container if necessary, put the object in, and confirm placement. Heating is only an intermediate milestone; it counts as complete only after the object has been placed at the destination. If the object is already in hand after taking, go directly to the heating stage without unnecessary restarting. After heating, if the object was indeed put into the microwave, take it out; if heating was completed while held in hand, keep holding it and go directly to the destination.

**When To Apply:** Any task that requires first heating an object and then placing it at a specified destination.

### T4_002: Explicit commands for microwave heating and recovery by switching position.

**Principle:** Open the microwave before using it, and confirm by observation that it is open. Use a heating form that explicitly specifies the object and the microwave, for example heat <object> with microwave <id>; bare generic forms such as use <object> or use microwave may return Nothing happens. Observations show that when heating, the object may be held in hand or may be placed in the open microwave, so the held/placed requirement should be handled according to observed conditions. If heating while held returns Nothing happens, you may put the object into the open microwave and retry; if heating the object inside the microwave fails, take the object out, confirm the microwave is open, and retry while holding it. After the first failure, change the object position or held state; do not repeat the exact same failed command; if there is still no confirmation after switching, switch back to the other state and retry once. Continue to the destination only after an explicit heating success is observed.

**When To Apply:** When the target object needs to be heated with the microwave, especially when the first heating attempt fails or the object is inside the microwave.

### T4_003: Failure Lesson

**Description:** The heating command may fail or return Nothing happens; if an unconfirmed attempt is treated as success, this may lead to moving and placing an object that is still cold. Heating success cannot be inferred merely because the object is held in hand or placed in the microwave.

**Why It Happens:** Heating can change state only when the object position and microwave state are suitable; issuing the command does not guarantee success. Without an explicit success observation, subsequent movement and placement may be based on a false premise.

**How To Avoid:** Continue only after an explicit heating success observation appears, such as a prompt that the object has been heated, or other reliable confirmation of the hot state. If success is not confirmed, correct the object position or held state, execute a valid heating attempt again, verify again, and then move the object.

### T4_004: Failure Lesson

**Description:** After microwave heating returns Nothing happens, switching without evidence to a stove, toaster, or other appliance may also fail or be blocked; substitutions based on assumptions only add failed steps. Accepting placement of an unheated object, or replacing the hot-state goal with ordinary cooling/no-heating actions, also cannot satisfy the task requirements.

**Why It Happens:** Some appliances may not support heating the target object, some surfaces may be occupied, and the existence of an alternative appliance does not guarantee that it supports the object. If placement is accepted without a confirmed hot state, the task may still fail even if the action was issued.

**How To Avoid:** First correct the microwave interaction: check whether it is open, adjust whether the object is held in hand or placed inside it, and retry without repeating the exact same failed command. Use another appliance only when the current observation explicitly shows that some alternative appliance supports heating the object and is available; otherwise do not treat the stove or toaster as a blind fallback. Do not treat ordinary placement or no-heating actions as a substitute for a confirmed hot state.

### T4_005: Systematic search when the target is missing.

**Principle:** When the target object is not at the first search location, continue systematically checking other possible containers and surfaces, such as cabinets, drawers, countertops, dining tables, stoves, refrigerators, sink basins, coffee machines, side tables, etc. Maintain a record of checked locations, prioritize turning to unchecked and already-open containers and visible surfaces, and avoid repeatedly returning to locations confirmed empty. Do not declare the task blocked or the object nonexistent merely because the first location is empty. If several consecutive containers are empty, expand to open surfaces and other container types rather than endlessly searching drawer by drawer; for dish-type objects, prioritize open surfaces such as dining tables, countertops, and side tables while also considering containers. After a broad search of reasonable scope, reassess rather than continuing to open every remaining container.

**When To Apply:** In the acquisition phase of a heat-then-place task, when the target object does not appear immediately or is not at the first checked location.

### T4_006: Failure Lesson

**Description:** When heating succeeds while the object is held, the object remains in the held state. Attempting to take the object from the microwave afterward may return Nothing happens, because that heating action did not put the object into the microwave.

**Why It Happens:** Heating successfully while held does not necessarily move the object into the microwave, so the object is not in the microwave to be taken. Continuing to act on the wrong location assumption produces invalid take steps.

**How To Avoid:** After successful held heating, confirm via inventory or held state that the object is still in hand, then go to the destination. Unless the object was actually put into the microwave, do not issue an action to take the object from the microwave.

### T4_007: Failure Lesson

**Description:** Inserting an extra countertop or other intermediate placement between heating and the final destination adds unnecessary actions and may cause object tracking or final placement to fail.

**Why It Happens:** The task may be over-decomposed, introducing an intermediate placement step even though the goal only requires moving the heated object to the final destination. Intermediate placement changes the object's location and adds state that must be tracked.

**How To Avoid:** After heating, pick up or keep holding the object, go directly to the final destination, and place it there. Add such intermediate placement steps only when the environment explicitly requires them.

## Executor — Cool then place

### T5_001: Cool an object and confirm its state before placement

**Principle:** Use environment feedback as authority. Acquire the exact target; go to the fridge and open it; while holding the target at the open fridge, use the available cooling interaction. If an explicit cool action is available, issue it for the target and fridge; otherwise use the available cooling interaction. Wait for a cooled-state confirmation before leaving. Then go to the destination, open it if closed, put the object there, and confirm placement. Do not treat mere containment, brief placement, or a fridge round-trip as confirmed cooling. Do not re-take an object already held; check inventory first. After successful cooling while holding, proceed directly to the destination rather than adding a take-from-fridge step.

**When To Apply:** When the goal requires an object to be cooled and then placed at a specified destination.

### T5_002: Failure Lesson

**Description:** An object found in the fridge, or briefly placed into it, may not be in the required cooled state. Cooling should be performed or verified explicitly before the object is taken to the destination.

**Why It Happens:** Storage location or containment can be mistaken for temperature state, and a fridge round-trip can be assumed to be sufficient cooling. The environment may change temperature only through an explicit cooling interaction.

**How To Avoid:** After opening the fridge and holding the target, use the available cool interaction and wait for a cooled-state confirmation. Do not immediately retrieve an object just placed in the fridge and treat it as cooled. If no cooled-state confirmation appears, do not assume success; retry or report the unresolved state through the available feedback channel.

### T5_003: Bounded search with early feasibility reassessment

**Principle:** Search a few high-probability locations first, such as the fridge, countertops, stove burners, dining table, cabinets, drawers, and shelves. Open containers as needed and track visited locations to avoid redundant loops. If the target is not in the fridge, continue a bounded systematic search across other plausible surfaces and containers rather than declaring failure after only opening the fridge. If the target is found on an accessible surface, take it directly and proceed. If it is not found after a reasonable broad search, reassess goal feasibility or possible absence rather than searching every unrelated receptacle. Do not repeat an identical broad search after obvious receptacles are exhausted; raise uncertainty early when feasibility is doubtful.

**When To Apply:** When the target object is not immediately visible or is missing from its expected location, and many storage receptacles exist.

### T5_004: Failure Lesson

**Description:** Placing the object directly without cooling, or stopping after opening the fridge or cooling the object without final placement, leaves the goal incomplete. The task requires both a cooled object and placement at the specified destination.

**Why It Happens:** The goal can be misread as simple placement, or cooling can be treated as the whole mission. Declaring completion after a partial step also causes failure.

**How To Avoid:** Treat cooling and final placement as separate checkpoints. Include an explicit cooling step before placement when a cool object is required, then continue to the destination and place the object. Do not declare success until both the cooled state and destination placement have been confirmed.

## Executor — Place two objects

### T6_001: Two-item sequential placement with per-item verification and placed-item tracking

**Principle:** Treat a two-item placement goal as two search-and-place cycles. For each cycle: locate and take one target object, navigate to the destination, open it if closed, place the object, and verify the placement from the observation before starting the next cycle. Track how many items are placed and which item was already placed; never take an already-placed item again. If a second take fails while an object is held, place the held object at the destination before returning for the second. If both instances are visible on the same surface or receptacle, place the first and then return to that same location for the second. If the final destination is temporarily unavailable, use only a safe recoverable holding location when necessary, then move both objects to the final destination afterward. Treat each placement as a checkpoint, not task completion.

**When To Apply:** When the goal requires placing two instances of the same object type at one target location and only one object can be carried at a time.

### T6_002: Systematic broad search with checked-location tracking

**Principle:** When targets are not immediately visible, search broadly. Inspect visible open surfaces (counters, tables, shelves, sofas) first, then open closed containers (cabinets, drawers) before inspecting or taking from inside. Continue across location types until the required instances are found or a checked-location record shows no unchecked likely locations remain. If both instances are visible on one surface, take one, place it, then return to that surface for the second. Treat an unreachable or no-change navigation target as unavailable and move to another candidate. Reassess feasibility after likely locations are exhausted, but do not conclude blocked prematurely.

**When To Apply:** When one or both target objects are not visible and must be located in the environment.

### T6_003: Failure Lesson

**Description:** Attempts to take a second object, or sometimes to move to another location, while already holding an object can return no effect. This blocks progress in two-item placement if the held object is not released first. A failed second take while an object is held should be diagnosed as the one-item carry limit, not as the second object being absent.

**Why It Happens:** The environment commonly allows carrying only one object at a time, so take or movement actions may be rejected while inventory is occupied.

**How To Avoid:** Before taking the second object or moving to search elsewhere, put the held object into the final destination or into a safe recoverable temporary location. Confirm the hands are empty, then continue. When a take fails while holding an object, attribute it to occupied inventory and place the held object first rather than concluding the target is missing.

### T6_004: Failure Lesson

**Description:** A put action can produce no effect if issued before reaching the destination receptacle, or it can fail without the failure being noticed. Continuing to search for the second item after an unconfirmed first placement can leave the goal unsatisfied. When a put returns no change, first verify that the actor is actually at the destination before concluding the receptacle rejects placement. If the destination repeatedly rejects placement after the location cause is ruled out, reassess whether it is valid and report blocked rather than looping or abandoning the held object.

**Why It Happens:** Placement requires being at the target container, and a successful put must be verified from the observation; otherwise the first item may still be held or not placed. Misattributing a location failure to receptacle type can lead to wrong alternative-destination actions, while some named destinations may be invalid or unreachable.

**How To Avoid:** Navigate to the destination before placing. After each put, inspect the observation to confirm success. If the put did not succeed, verify the current location, move to the target if needed, and retry before starting the next search or placement cycle. Do not switch to an alternative receptacle until the destination-location cause has been ruled out; if repeated rejection continues, reassess validity and report blocked.

### T6_005: Failure Lesson

**Description:** Attempting to put an object into, or take an object from, a closed cabinet, drawer, or similar container may produce no effect. Issuing open on an already-open container may also return no change and should not be retried. Issuing open on a container while standing at its parent furniture may return no change; the actor must navigate to the container itself first.

**Why It Happens:** The environment requires the container to be open before its contents can be accessed or modified, reports no change when opening an already-open container, and validates open actions against the actor's current location being the container rather than its parent furniture.

**How To Avoid:** Navigate to the container itself, then open it with the appropriate open action. If it is already open, or if opening returns no change, proceed to take or place rather than retrying open. After opening, verify access before taking or placing. Do not issue open on a container from its parent furniture.

### T6_006: Failure Lesson

**Description:** Using an examine-style action on objects or locations is not supported and returns no useful information.

**Why It Happens:** The available interaction set is limited to navigation, taking, putting, opening, and inventory-style operations; examining is not an effective substitute.

**How To Avoid:** Inspect a location by navigating to the receptacle and observing its contents. Pick up visible target objects with a take action from that receptacle.

### T6_007: Failure Lesson

**Description:** Placing an object into a non-target or unsuitable container such as a garbage can can make retrieval impossible or cause the overall two-item placement to fail.

**Why It Happens:** Some containers may not accept objects cleanly, may change object state, or may not allow reliable retrieval; temporary storage is only safe if the object can be taken back.

**How To Avoid:** Prefer placing the first object directly into the final destination. If temporary holding is unavoidable, choose an open, stable, recoverable surface or container and avoid garbage cans or other likely irreversible containers.

### T6_008: Failure Lesson

**Description:** After several containers have been opened and no target found, repeatedly revisiting locations already confirmed empty, re-taking an already-placed instance, repeating a no-change navigation, or trying yet another receptacle after many failed put attempts can exhaust the action budget and cause failure. A held object whose put attempts fail across many receptacles may indicate an unplaceable object or an infeasible goal rather than a wrong receptacle.

**Why It Happens:** Searching without tracking checked locations and placed instances leads to redundant actions, while unchecked opened containers or visible surfaces may still contain the target. A no-change navigation indicates the target location is unreachable or invalid, so retrying it cannot help.

**How To Avoid:** Maintain a list of checked locations and placed instances. Prioritize unchecked opened containers and visible surfaces; take a target directly if it is visible. Avoid revisiting a location confirmed to have no target or re-taking an already-placed object unless new evidence suggests otherwise. After one no-change navigation, choose a different unchecked location. If every put attempt fails across many receptacles, stop suggesting new receptacles and reassess the held object's exact identifier and whether the destination accepts placement, considering the object unplaceable or the goal infeasible.

### T6_009: Failure Lesson

**Description:** Repeatedly declaring a subtask complete without executing the required next action can trigger a loop guard and terminate the episode before the two items are placed. Re-taking an already-placed item and re-placing it at a different instance of the destination can also trigger a guard.

**Why It Happens:** The current state may be misread as satisfying the completion condition even though the actual goal or subgoal is unfinished, causing repeated signals instead of progress; alternatively, the destination instance may be confused, leading to re-taking a placed item.

**How To Avoid:** Signal completion only after the corresponding subgoal is actually achieved, such as an object being taken or placed. After signaling, continue with the necessary next action and avoid repeating the same completion signal without new progress. Track which destination instance is the goal; once an item is placed at the target, do not re-take it—search for a second instance instead.

## Critic — General

### G_001: Search observable surfaces first, then broaden to closed containers

**Principle:** When the target object's location is unknown, locate it before manipulation by checking open, directly observable surfaces and common holding places first: tables, countertops, desks, dressers, shelves, beds, sofas, chairs, and other plausible visible surfaces such as toilets or TV stands when they could hold the target. Only then open closed containers such as drawers, cabinets, fridges, microwaves, and similar receptacles. Treat search as a broad multi-location search rather than assuming one named receptacle contains the object. If an early location is empty, broaden to other plausible unchecked locations. If the target or a required fixture is already visible on a surface, go directly to that furniture instead of continuing unrelated container checks.

**When To Apply:** When the target object's location is unknown at the start, when the first checked location does not contain it, or when the target or a required fixture is already visible on a surface.

### G_002: Failure Lesson

**Description:** Failed searches often repeat the same empty surfaces or failed take attempts, revisit already-confirmed-empty locations, or conclude the object is unavailable before all plausible open surfaces and relevant containers have been checked. A search should maintain a checked-location list and move to a new unchecked plausible location after a failed take or empty look.

**Why It Happens:** Search may be treated as an unconstrained sequence without bookkeeping, so empty locations are revisited and some plausible locations are never examined; alternatively, failure may be declared after only a subset of locations is checked.

**How To Avoid:** Record each checked location and its result. After a failed take or empty look, mark that location checked and move to another plausible unchecked location. Do not revisit confirmed empty surfaces unless the environment state changed. Open closed receptacles before treating them as searched and prioritize locations by object type. If the object remains absent after relevant locations are exhausted, report failure rather than continuing indefinitely; but do not declare blocked while plausible unchecked locations remain.

### G_003: Open closed containers before taking or placing and verify destination openability

**Principle:** When a closed drawer, cabinet, safe, fridge, microwave, or similar container may hold the target or is the placement destination, navigate to it and open it before attempting to take from it or put into it. Closed containers cannot be inspected or used directly. Before placing, confirm the destination is already open or can be opened; if opening returns no change, treat it as non-openable and choose a valid open destination or surface. For non-openable fixtures, use only a go-then-put sequence.

**When To Apply:** When the target may be inside a closed container, or when the placement destination is closed or its openability is uncertain.

### G_004: Position at the object's receptacle before take and at the destination before put

**Principle:** A take action succeeds only when the actor is at the receptacle where the object is present, and a put action succeeds only when the actor is at the destination. When retrieving, first locate the object and position at its receptacle before taking. Once the target is held, travel directly to the specified destination and place it without unnecessary intermediate steps; if a put fails, verify current location and navigate to the destination before retrying.

**When To Apply:** When retrieving an object whose location is not current, when moving a held object to a destination, or after a failed put.

### G_005: Use supported action forms, exact identifiers, and matching object instances

**Principle:** Use only supported action forms: go to a location, take an object from a receptacle, put an object in or on a receptacle, open a container before accessing it, and use a fixture with its numbered instance when applicable. Refer to exact object and receptacle identifiers from observations, including instance numbers, and track the specific instance taken so later actions use the same one. Prefer navigating to locations, furniture, or receptacles rather than to a takeable object when the action form requires it. Do not use examine, look at, or open on non-container surfaces; open only applies to openable containers. Before taking or transforming, confirm the object name matches the goal, because similar types may not satisfy it. If many containers have been checked without success, reassess visible surfaces and the target description rather than continuing blind exhaustive checks.

**When To Apply:** Throughout object search, retrieval, and placement, especially when forming commands or when an action seems unsupported or ambiguous.

### G_006: Failure Lesson

**Description:** When an action such as go to, open, take, put, use, or clean returns no change, do not repeat the same command. Failed attempts can come from being at the wrong location, using an inexact or invalid identifier, targeting a closed or non-openable receptacle, or trying an inaccessible location. Treat an unreachable navigation target as unavailable and switch to another candidate; treat an already-open container as open and continue rather than reopening it. Repeated no-change results are evidence that the current approach is exhausted.

**Why It Happens:** The same invalid action may be retried without updating the inferred state, and a failed task segment may be reissued identically instead of changing the search location, object description, or strategy.

**How To Avoid:** After a no-change observation, re-check location, inventory, exact identifiers, and object or container state. Change at least one relevant condition: move to a different reachable location, open a closed container, use the specific instance id, or switch to another strategy. After one or two identical failures, stop retrying. If a task segment fails or returns without meeting its condition, do not repeat it unchanged; broaden the search or change the approach. Before declaring blocked, ensure every plausible closed container was actually opened and inspected, not merely approached, and avoid revisiting surfaces already confirmed empty.

### G_007: Separate acquisition from operation with observable completion conditions

**Principle:** For tasks that require an object to be found and then manipulated, cleaned, heated, cooled, examined, or placed, split the task into an acquisition phase and an operation phase. The acquisition phase ends only when the target object is actually held, not merely seen and not merely because a container was opened. The operation phase ends only when the environment observation confirms the required final state, such as the object being at the destination, cleaned, heated, or cooled. Begin placement only after acquisition is confirmed by holding the target object. If a subsequent phase or handoff follows, report acquisition only after the take observation confirms holding and note any remaining operation.

**When To Apply:** When a goal requires an object to be acquired before it is used, transformed, or placed, and the object is not already held.

### G_008: Failure Lesson

**Description:** Do not declare completion or stop based on an attempted action alone. After critical actions such as take, put, clean, heat, or cool, inspect the observation for the goal predicate. Declare success only when the observation confirms the required final state; declare failure only when the observation shows an invalid or blocked action, an unreachable object, or exhaustion of plausible locations. If the placement observation already confirms the goal, treat it as terminal and do not run a redundant verification step.

**Why It Happens:** An action may be assumed successful without checking feedback, failure may be declared after a successful sequence, or an unnecessary verification step may be added after success, causing loops.

**How To Avoid:** After each critical action, compare the observation with the expected state. If the action failed, retry only after adjusting the approach; if it succeeded, stop issuing extra actions. Treat a confirming placement, cleaning, heating, or cooling observation as the terminal success condition. Do not declare completion before the final placement is confirmed; after confirmation, stop and do not send empty or inventory-only actions.

## Critic — Simple pick-and-place

### T1_001: Simple pick-and-place procedure

**Principle:** For a simple pick-and-place goal, decompose the task into two ordered subtasks: first locate and take the target object, then move to the specified destination and put the object down.

**When To Apply:** When the goal is to move a single object to a specified destination and no additional state change such as cleaning, heating, cooling, or lighting is required.

## Critic — Examine with desk lamp

### T2_001: Desklamp observation: locate the target object and use the numbered desklamp at the furniture where the desklamp is located.

**Principle:** First confirm the locations of the target object and the desklamp. The desklamp is usually fixed on a furniture surface; after observing the desklamp, go directly to the furniture where it is located, do not continue searching unrelated containers or blindly open drawers, and do not treat the desklamp as a carryable item or navigation point. If the target object is not at the desklamp, first obtain it and carry it to that furniture; if the target object is already at the desklamp, first ensure the target object is in hand before interacting. Upon arrival, use the numbered instance with use desklamp <id> to trigger observation; do not use the bare name or compound syntax. Successfully turning on the desklamp is the termination condition; do not append use/look after it; if the target object has already been obtained at that furniture, do not go to the same location again.

**When To Apply:** When the task requires examine/look at something with/under the desklamp, and an interactable desklamp exists in the environment.

### T2_002: Failure Lesson

**Description:** Multiple failed trajectories show that take desklamp, go to desklamp, or repeatedly going to the desklamp/desktop usually returns Nothing happens, wasting steps and possibly blocking subsequent observation; the desklamp is an interaction point fixed on furniture, not a carryable item or navigable location.

**Why It Happens:** The environment models the desklamp as a fixed light source or fixed device; only the furniture where it is located can be a navigation target, and the desklamp itself cannot be the target of take or go to.

**How To Avoid:** Do not attempt to take, move, or navigate to the desklamp. First reach the furniture bearing the desklamp (desk, sidetable, dresser, coffeetable, etc.); once there, directly use the numbered use desklamp <id>; if already at the desklamp, do not go to the same location again.

### T2_003: Failure Lesson

**Description:** In failed trajectories, examine X with desklamp, examine the target object, examine desklamp, examine furniture (such as examine desk 1), bare-name use desklamp, use desklamp on X, use X on desklamp often return There's nothing special about X or Nothing happens, and cannot substitute for the observation condition. Merely placing the target object on the desk or desklamp without triggering the desklamp interaction also causes the task to appear complete while the environment goal is not achieved. The valid interaction form is to use the observed numbered lamp instance, for example use desklamp 1.

**Why It Happens:** The environment does not support using the desklamp as a tool argument to examine, nor does it support bare names or compound syntax; examining furniture also does not provide effective information; the placement action itself does not trigger the observation success condition.

**How To Avoid:** After locating the target object and bringing it to the furniture where the desklamp is located, use the observed numbered lamp instance to execute use desklamp <id>. Do not use examine X with desklamp, examine the target object/desklamp/furniture, or compound use syntax; if invalid syntax has been attempted, verify the desklamp instance name and retry, rather than repeatedly examining.

### T2_004: Failure Lesson

**Description:** If use desklamp returns Nothing happens, it usually means you are not currently at the desklamp's location, the current furniture observation does not include a desklamp, a bare name was used instead of a numbered instance, or the target object has not been obtained/the interaction conditions are not met; repeating the same use/examine/look command at the same location will not change the state and may form a loop or trigger protection. After one or two consecutive failures, stop repeating.

**Why It Happens:** Using the desklamp requires being at the same location as the furniture where the desklamp is located, and incorrect syntax (such as bare-name use desklamp), location, or not holding the target object will not produce a state change; mistaking an empty observation for a retry signal will repeat invalid actions.

**How To Avoid:** After a failure, first check whether the current furniture observation actually lists desklamp; if not, move to another furniture where a desklamp has been observed, rather than retrying the same use. If the desklamp is present, ensure the target object has been obtained or is held, then retry with the numbered use desklamp <id>; if there is still no change, search other locations or declare that it cannot be completed, and do not repeat the same command or fall back to examine.

### T2_005: Desklamp observation search strategy: prioritize open surfaces, then systematically check containers.

**Principle:** When searching for the target object or the desklamp, prioritize checking open surfaces related to the desklamp, such as desk, sidetable, nightstand, bed, dresser, sofa, coffeetable, armchair, shelf, etc.; once the desklamp is observed, go directly to the furniture where it is located and use the desklamp if needed, do not continue traversing many drawers or irrelevant containers. If the target object is not on reasonable open surfaces, then systematically search by container type (drawer/cabinet), and after finding it return to the desklamp. Avoid repeatedly look/examine the same location; when there is no new information, turn to other furniture or containers. 'under the desklamp' does not guarantee that the target object or the desklamp is necessarily at the assumed location, so when the assumed location is not visible, search other surfaces and containers.

**When To Apply:** When searching for the target object or desklamp in a desklamp observation task, or when you have reached the assumed desklamp location but the target object or desklamp is not there and repeated observations yield no new information.

## Critic — Clean then place

### T3_001: Clean-then-place sequence with verified cleaning

**Principle:** For a goal requiring a clean object to be placed, use separate stages: locate and acquire the named target; bring it to a compatible cleaning fixture, preferring a sinkbasin; clean it; verify from the observation that cleaning succeeded; then go to the destination, open it if closed, and place the object. Do not place before cleaning, and do not mark cleaning complete without confirming evidence. If cleaning did not succeed, return to the cleaning stage before placement. If transfer or handoff occurs after acquisition, record that cleaning is still required. Treat successful placement as the terminal condition.

**When To Apply:** When the goal is to put a clean object in or on a specified receptacle and the object is not already clean.

### T3_002: Failure Lesson

**Description:** A clean action may produce no effect when the target is not held, the current location is not a valid cleaning fixture, or the object is unsuitable. Cleaning is reliably supported at a sinkbasin in observations; alternatives such as bathtubbasin or fridge should not be assumed equivalent. Repeated identical clean attempts waste steps. Trying to take another object while still holding the failed object may also produce repeated no-ops.

**Why It Happens:** The environment appears to validate that the object is held and that cleaning occurs at a compatible fixture; not every fixture or object supports cleaning.

**How To Avoid:** Hold the target, navigate to a sinkbasin, then clean. If no effect, verify the held object and current location; try a different sinkbasin or confirm the object is cleanable. Treat bathtubbasin as unverified and switch to sinkbasin if it fails. After a failed clean, either try a different cleanable candidate after releasing the held object at a valid surface or report the object as not cleanable; do not loop on the same action.

### T3_003: Failure Lesson

**Description:** Some objects, such as towels or cloth, may not support the clean action at a sinkbasin; repeated clean attempts can keep failing. This may mean the object type is not cleanable or the selected object is not the intended cleanable item.

**Why It Happens:** Not every object type supports cleaning, and the chosen item may not be the task's intended cleanable target.

**How To Avoid:** Before committing to an object, choose a likely cleanable candidate. If clean returns no effect after confirming the fixture and that the object is held, stop repeating clean; try another candidate or report that the object is not cleanable.

### T3_004: Failure Lesson

**Description:** Placement can fail when the destination container is closed, has no available space, or is not a valid receptacle. Some fixtures, such as toilets or coffeemachines, may reject placement; repeated put/open/use on a coffeemachine can return no effect. An open action may also return no effect when the container is already open or not openable.

**Why It Happens:** Containers may require opening or have capacity limits, and some fixtures are not valid placement targets; repeating put or open without changing conditions can waste steps.

**How To Avoid:** Before placing, open a closed destination. If open returns no effect, do not retry it; treat it as already open or non-openable and proceed or reassess. Check space or availability when possible. If the destination is invalid or put repeatedly has no effect, seek an alternative valid destination or report blocked rather than looping.

### T3_005: Failure Lesson

**Description:** Goals specify an object type. Similar alternatives such as mug for cup, pan for pot, or butterknife for knife should not be silently substituted. A close synonym may be used only if the exact object is unavailable and the environment or observation explicitly treats it as equivalent, or the goal permits it; otherwise continue searching or report the mismatch. If the destination already contains a similar object, still acquire, clean, and place the correct target rather than swapping.

**Why It Happens:** Generalizing categories can cause taking the wrong item and failing the task, while exact-name matching may miss an accepted synonym; equivalence must be confirmed rather than assumed.

**How To Avoid:** Search first for the exact named type. If not found, do not swap in a different type by default; use only a confirmed equivalent. Confirm equivalence through explicit environmental or observational evidence or goal permission before substituting.

### T3_006: Failure Lesson

**Description:** Search should prioritize plausible locations but avoid opening every remaining container indefinitely or declaring blocked prematurely. Track checked locations and avoid revisiting confirmed-empty ones. After a reasonable set of likely locations has been checked—not merely one or two when many plausible ones remain—consider unusual placement or impossibility, then reassess or report blocked.

**Why It Happens:** Item locations may follow regularities, but unusual placement or impossible tasks can occur; unbounded search wastes steps and can cause timeout, while stopping too early can miss findable objects.

**How To Avoid:** Prioritize likely locations by object type: food-related items in fridge; dishes or utensils in countertop, cabinet, or drawer; cleaning supplies near sinkbasin, countertop, or shelf. Keep a record of checked locations. After several likely locations fail, consider unusual placement or impossibility and reassess or report blocked rather than exhaustively opening all containers or stopping after only a couple of empty locations.

## Critic — Heat then place

### T4_001: End-to-end process of heating first, then placing.

**Principle:** For a target that is heated first and then placed: locate and take the target object, go to the microwave, open it if closed, complete heating in a way confirmed feasible by observation, and continuously track the same object instance; then go to the final destination, open the container if necessary, put the object in, and confirm placement. Heating is only an intermediate milestone; it counts as complete only after the object has been placed at the destination. If the object is already in hand after taking, go directly to the heating stage without unnecessary restarting. After heating, if the object was indeed put into the microwave, take it out; if heating was completed while held in hand, keep holding it and go directly to the destination.

**When To Apply:** Any task that requires first heating an object and then placing it at a specified destination.

### T4_002: Explicit commands for microwave heating and recovery by switching position.

**Principle:** Before using the microwave, open it first and confirm by observation that it is open. Use a heating form that explicitly specifies the object and microwave, e.g. heat <object> with microwave <id>; bare generic forms such as use <object> or use microwave may return Nothing happens. Observations show that heating can occur while the object is held or after it is placed in the open microwave. If held heating returns Nothing happens, a reliable recovery is to put the object into the open microwave, take it back out, then retry heating while held; if heating fails while the object is inside the microwave, take the object out, confirm the microwave is open, and retry while held. After a first failure, change the object's location or held state; do not repeat the exact same failing command; if there is still no confirmation after switching, switch back to the other state and retry once. Proceed to the destination only after observing explicit heating success.

**When To Apply:** When the target object needs to be heated with the microwave, especially when the first heating attempt fails or the object is inside the microwave.

### T4_003: Failure Lesson

**Description:** The heating command may fail or return Nothing happens; treating an unconfirmed attempt as success may lead to moving and placing an object that is still cold. The Critic often misjudges that the object "has been put into the microwave" or "is now in the microwave," while observations only show the microwave was opened or the object is still held; this misjudgment drives wrong next steps. Heating success cannot be inferred merely from the object being held or placed in the microwave.

**Why It Happens:** Heating can change state only when the object's location and the microwave's state are suitable; issuing the command does not guarantee success. Without explicit success observation, subsequent moving and placing may rest on a false premise, and misreading "microwave opened" or "still held" as "placed/heated" further amplifies the error.

**How To Avoid:** Before giving the next-step suggestion, cite the actual observation predicate (held or in-container). Continue only after an explicit heating-success observation appears, such as a prompt that the object has been heated, or other reliable heat-state confirmation. If success is unconfirmed, correct the object's location or held state, re-execute a valid heating attempt, verify again, and then move the object.

### T4_004: Failure Lesson

**Description:** After microwave heating returns Nothing happens, switching without evidence to a stove, toaster, or other appliance may also fail or be blocked; substitutions based on assumptions only add failed steps. Accepting placement of an unheated object, or replacing the hot-state goal with ordinary cooling/no-heating actions, also cannot satisfy the task requirements.

**Why It Happens:** Some appliances may not support heating the target object, some surfaces may be occupied, and the existence of an alternative appliance does not guarantee that it supports the object. If placement is accepted without a confirmed hot state, the task may still fail even if the action was issued.

**How To Avoid:** First correct the microwave interaction: check whether it is open, adjust whether the object is held in hand or placed inside it, and retry without repeating the exact same failed command. Use another appliance only when the current observation explicitly shows that some alternative appliance supports heating the object and is available; otherwise do not treat the stove or toaster as a blind fallback. Do not treat ordinary placement or no-heating actions as a substitute for a confirmed hot state.

### T4_005: Systematic search when the target is missing.

**Principle:** When the target object is not at the first search location, continue systematically checking other possible containers and surfaces, such as cabinets, drawers, countertops, dining tables, stoves, refrigerators, sink basins, coffee machines, side tables, etc. Maintain a record of checked locations, prioritize turning to unchecked and already-open containers and visible surfaces, and avoid repeatedly returning to locations confirmed empty. Do not declare the task blocked or the object nonexistent merely because the first location is empty. If several consecutive containers are empty, expand to open surfaces and other container types rather than endlessly searching drawer by drawer; for dish-type objects, prioritize open surfaces such as dining tables, countertops, and side tables while also considering containers. After a broad search of reasonable scope, reassess rather than continuing to open every remaining container.

**When To Apply:** In the acquisition phase of a heat-then-place task, when the target object does not appear immediately or is not at the first checked location.

### T4_006: Failure Lesson

**Description:** When heating succeeds while the object is held, the object remains in the held state. Attempting to take the object from the microwave afterward may return Nothing happens, because that heating action did not put the object into the microwave. The Critic should diagnose accordingly: a failed take from microwave means the object was never in the microwave, not that another take is needed.

**Why It Happens:** Heating successfully while held does not necessarily move the object into the microwave, so the object is not in the microwave to be taken. Continuing to act on the wrong location assumption produces invalid take steps.

**How To Avoid:** After successful held heating, confirm via inventory or held state that the object is still in hand, then go to the destination. Unless the object was actually put into the microwave, do not issue an action to take the object from the microwave; if take from microwave returns Nothing happens, check the held state rather than repeating the take.

### T4_007: Failure Lesson

**Description:** Inserting an extra countertop or other intermediate placement between heating and the final destination adds unnecessary actions and may cause object tracking or final placement to fail.

**Why It Happens:** The task may be over-decomposed, introducing an intermediate placement step even though the goal only requires moving the heated object to the final destination. Intermediate placement changes the object's location and adds state that must be tracked.

**How To Avoid:** After heating, pick up or keep holding the object, go directly to the final destination, and place it there. Add such intermediate placement steps only when the environment explicitly requires them.

## Critic — Cool then place

### T5_001: Cool an object and confirm its state before placement

**Principle:** Use environment feedback as authority. Acquire the exact target; go to the fridge and open it; while holding the target at the open fridge, use the available cooling interaction. If an explicit cool action is available, issue it for the target and fridge; otherwise use the available cooling interaction. Wait for a cooled-state confirmation before leaving. Then go to the destination, open it if closed, put the object there, and confirm placement. Do not treat mere containment, brief placement, or a fridge round-trip as confirmed cooling. Do not re-take an object already held; check inventory first. After successful cooling while holding, proceed directly to the destination rather than adding a take-from-fridge step.

**When To Apply:** When the goal requires an object to be cooled and then placed at a specified destination.

### T5_002: Failure Lesson

**Description:** An object found in the fridge, or briefly placed into it, may not be in the required cooled state. Cooling should be performed or verified explicitly before the object is taken to the destination.

**Why It Happens:** Storage location or containment can be mistaken for temperature state, and a fridge round-trip can be assumed to be sufficient cooling. The environment may change temperature only through an explicit cooling interaction.

**How To Avoid:** After opening the fridge and holding the target, use the available cool interaction and wait for a cooled-state confirmation. Do not immediately retrieve an object just placed in the fridge and treat it as cooled. If no cooled-state confirmation appears, do not assume success; retry or report the unresolved state through the available feedback channel.

### T5_003: Bounded search with early feasibility reassessment

**Principle:** Search a few high-probability locations first, such as the fridge, countertops, stove burners, dining table, cabinets, drawers, and shelves. Open containers as needed and track visited locations to avoid redundant loops. Distinguish 'arrived at a closed container' from 'inspected and empty': a closed container's contents are unverified until opened. If the target is not in the fridge, continue a bounded systematic search across other plausible surfaces and containers rather than declaring failure after only opening the fridge. If the target is found on an accessible surface, take it directly and proceed. If it is not found after a reasonable broad search, reassess goal feasibility or possible absence rather than searching every unrelated receptacle. Do not repeat an identical broad search after obvious receptacles are exhausted; raise uncertainty early when feasibility is doubtful.

**When To Apply:** When the target object is not immediately visible or is missing from its expected location, and many storage receptacles exist.

### T5_004: Failure Lesson

**Description:** Placing the object directly without cooling, or stopping after opening the fridge or cooling the object without final placement, leaves the goal incomplete. The task requires both a cooled object and placement at the specified destination.

**Why It Happens:** The goal can be misread as simple placement, or cooling can be treated as the whole mission. Declaring completion after a partial step also causes failure.

**How To Avoid:** Treat cooling and final placement as separate checkpoints. Include an explicit cooling step before placement when a cool object is required, then continue to the destination and place the object. Do not declare success until both the cooled state and destination placement have been confirmed.

## Critic — Place two objects

### T6_001: Two-item sequential placement with per-item verification and placed-item tracking

**Principle:** Treat a two-item placement goal as two search-and-place cycles. For each cycle: locate and take one target object, navigate to the destination, open it if closed, place the object, and verify the placement from the observation before starting the next cycle. Track how many items are placed and which item was already placed; never take an already-placed item again. If a second take fails while an object is held, place the held object at the destination before returning for the second. If both instances are visible on the same surface or receptacle, place the first and then return to that same location for the second. If the final destination is temporarily unavailable, use only a safe recoverable holding location when necessary, then move both objects to the final destination afterward. Treat each placement as a checkpoint, not task completion.

**When To Apply:** When the goal requires placing two instances of the same object type at one target location and only one object can be carried at a time.

### T6_002: Systematic broad search with checked-location tracking

**Principle:** When target objects are not immediately visible, search broadly rather than checking only one receptacle type. Inspect visible open surfaces such as counters, tables, shelves, sofas, and similar surfaces first, then check closed containers such as cabinets and drawers, opening them before inspecting or taking from inside. Continue across multiple location types until the required number of instances is found or a checked-location record shows no remaining unchecked likely locations. If both target instances are visible on the same surface, take one, place it, then return to that same surface for the second rather than wandering to unrelated containers. Treat an unreachable or no-change navigation target as unavailable and move to another candidate. Reassess feasibility after likely locations are exhausted, but do not conclude the task is blocked prematurely.

**When To Apply:** When one or both target objects are not visible and must be located in the environment.

### T6_003: Failure Lesson

**Description:** Attempts to take a second object, or sometimes to move to another location, while already holding an object can return no effect. This blocks progress in two-item placement if the held object is not released first. A failed second take while an object is held should be diagnosed as the one-item carry limit, not as the second object being absent.

**Why It Happens:** The environment commonly allows carrying only one object at a time, so take or movement actions may be rejected while inventory is occupied.

**How To Avoid:** Before taking the second object or moving to search elsewhere, put the held object into the final destination or into a safe recoverable temporary location. Confirm the hands are empty, then continue. When a take fails while holding an object, attribute it to occupied inventory and place the held object first rather than concluding the target is missing.

### T6_004: Failure Lesson

**Description:** A put action can produce no effect if issued before reaching the destination receptacle, or it can fail without the failure being noticed. Continuing to search for the second item after an unconfirmed first placement can leave the goal unsatisfied. When a put returns no change, first verify that the actor is actually at the destination before concluding the receptacle rejects placement; a subsequent go-to-destination followed by a retried put often succeeds. If the destination repeatedly rejects placement after the location cause is ruled out, reassess whether it is valid and report blocked rather than looping or abandoning the held object.

**Why It Happens:** Placement requires being at the target container, and a successful put must be verified from the observation; otherwise the first item may still be held or not placed. Misattributing a location failure to receptacle type can lead to wrong alternative-destination actions, while some named destinations may be invalid or unreachable.

**How To Avoid:** Navigate to the destination before placing. After each put, inspect the observation to confirm success. If the put did not succeed, verify the current location, move to the target if needed, and retry before starting the next search or placement cycle. Do not switch to an alternative receptacle until the destination-location cause has been ruled out; if repeated rejection continues, reassess validity and report blocked.

### T6_005: Failure Lesson

**Description:** Attempting to put an object into, or take an object from, a closed cabinet, drawer, or similar container may produce no effect. Issuing open on an already-open container may also return no change and should not be retried. Issuing open on a container while standing at its parent furniture may return no change; the actor must navigate to the container itself first.

**Why It Happens:** The environment requires the container to be open before its contents can be accessed or modified, reports no change when opening an already-open container, and validates open actions against the actor's current location being the container rather than its parent furniture.

**How To Avoid:** Navigate to the container itself, then open it with the appropriate open action. If it is already open, or if opening returns no change, proceed to take or place rather than retrying open. After opening, verify access before taking or placing. Do not issue open on a container from its parent furniture.

### T6_006: Failure Lesson

**Description:** Using an examine-style action on objects or locations is not supported and returns no useful information.

**Why It Happens:** The available interaction set is limited to navigation, taking, putting, opening, and inventory-style operations; examining is not an effective substitute.

**How To Avoid:** Inspect a location by navigating to the receptacle and observing its contents. Pick up visible target objects with a take action from that receptacle.

### T6_007: Failure Lesson

**Description:** Placing an object into a non-target or unsuitable container such as a garbage can can make retrieval impossible or cause the overall two-item placement to fail.

**Why It Happens:** Some containers may not accept objects cleanly, may change object state, or may not allow reliable retrieval; temporary storage is only safe if the object can be taken back.

**How To Avoid:** Prefer placing the first object directly into the final destination. If temporary holding is unavoidable, choose an open, stable, recoverable surface or container and avoid garbage cans or other likely irreversible containers.

### T6_008: Failure Lesson

**Description:** After several containers have been opened and no target found, repeatedly revisiting locations already confirmed empty, re-taking an already-placed instance, repeating a no-change navigation, or trying yet another receptacle after many failed put attempts can exhaust the action budget and cause failure. A held object whose put attempts fail across many receptacles may indicate an unplaceable object or an infeasible goal rather than a wrong receptacle. Critic should not assert a specific unseen location contains the target or that a failed action was 'transient' without observed evidence.

**Why It Happens:** Searching without tracking checked locations and placed instances leads to redundant actions, while unchecked opened containers or visible surfaces may still contain the target. A no-change navigation indicates the target location is unreachable or invalid, so retrying it cannot help; speculation about unseen contents or transient failures drives further wasted steps.

**How To Avoid:** Maintain a list of checked locations and placed instances. Prioritize unchecked opened containers and visible surfaces; take a target directly if it is visible. Avoid revisiting a location confirmed to have no target or re-taking an already-placed object unless new evidence suggests otherwise. After one no-change navigation, choose a different unchecked location. Base advice on observed state rather than asserting unseen contents or transient failures. If every put attempt fails across many receptacles, stop suggesting new receptacles and reassess the held object's exact identifier and whether the destination accepts placement, considering the object unplaceable or the goal infeasible.

### T6_009: Failure Lesson

**Description:** Repeatedly declaring a subtask complete without executing the required next action can trigger a loop guard and terminate the episode before the two items are placed. Re-taking an already-placed item and re-placing it at a different instance of the destination can also trigger a guard.

**Why It Happens:** The current state may be misread as satisfying the completion condition even though the actual goal or subgoal is unfinished, causing repeated signals instead of progress; alternatively, the destination instance may be confused, leading to re-taking a placed item.

**How To Avoid:** Signal completion only after the corresponding subgoal is actually achieved, such as an object being taken or placed. After signaling, continue with the necessary next action and avoid repeating the same completion signal without new progress. Track which destination instance is the goal; once an item is placed at the target, do not re-take it—search for a second instance instead.

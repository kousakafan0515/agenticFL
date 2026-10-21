# English reference: global_skillbank3.json

Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.

## Global — General

### G_001: Search observable surfaces before closed containers

**Principle:** When an object's location is unknown, locate it before manipulation. First check open, directly observable surfaces and common holding places such as tables, countertops, desks, dressers, shelves, beds, sofas, chairs, and other plausible visible surfaces; then open closed containers such as drawers, cabinets, fridges, and microwaves. Treat search as a broad multi-location search rather than assuming a named receptacle contains the target. If an early location is empty, broaden to other plausible unchecked locations. If the target or a needed fixture is already visible on a surface, go directly to that furniture instead of continuing unrelated container checks.

**When To Apply:** When the target location is unknown, when the first checked location is empty, or when the target or a required fixture is already visible on a surface.

### G_002: Avoid repeated or incomplete search bookkeeping

**Description:** Failed searches often repeat the same empty surfaces or failed take attempts, revisit locations already confirmed empty, or conclude the object is unavailable before all plausible open surfaces and relevant containers have been checked.

**Why It Happens:** Search may be treated as an unconstrained sequence without bookkeeping, so empty locations are revisited and plausible locations are missed; failure may also be declared after checking only a subset.

**How To Avoid:** Record each checked location and result. After a failed take or empty look, mark that location checked and move to another plausible unchecked location. Do not revisit confirmed empty surfaces unless the state changed. Open closed receptacles before treating them as searched, and prioritize locations by object type. If the object remains absent after relevant locations are exhausted, report failure rather than continuing indefinitely; do not declare blocked while plausible unchecked locations remain.

### G_003: Open closed containers before access and verify destination openability

**Principle:** When a closed drawer, cabinet, safe, fridge, microwave, or similar container may hold the target or is the placement destination, navigate to it and open it before attempting to take from it or put into it. Closed containers cannot be inspected or used directly. Before placing, confirm the destination is already open or can be opened; if opening returns no change, treat it as non-openable and choose a valid open destination or surface. For non-openable fixtures, use only a go-then-put sequence.

**When To Apply:** When the target may be inside a closed container, or when the placement destination is closed or its openability is uncertain.

### G_004: Position at the source receptacle before take and at the destination before put

**Principle:** A take action succeeds only when at the receptacle where the object is present, and a put action succeeds only when at the destination. When retrieving, first locate the object and position at its receptacle before taking. Once the target is held, travel directly to the specified destination and place it without unnecessary intermediate steps; if a put fails, verify current location and navigate to the destination before retrying.

**When To Apply:** When retrieving an object whose location is not current, when moving a held object to a destination, or after a failed put.

### G_005: Use supported actions, exact identifiers, and matching object instances

**Principle:** Use only supported action forms: go to a location, take an object from a receptacle, put an object in or on a receptacle, open a container before accessing it, and use a fixture with its numbered instance when applicable. Refer to exact object and receptacle identifiers from observations, including instance numbers, and track the specific instance taken so later actions use the same one. Prefer navigating to locations, furniture, or receptacles rather than to a takeable object when the action form requires it. Do not use examine, look at, or open on non-container surfaces; open only applies to openable containers. Before taking or transforming, confirm the object name matches the goal, because similar types may not satisfy it. If many containers have been checked without success, reassess visible surfaces and the target description rather than continuing blind exhaustive checks.

**When To Apply:** Throughout object search, retrieval, and placement, especially when forming commands or when an action seems unsupported or ambiguous.

### G_006: Change the approach after a no-change action result

**Description:** When an action such as go to, open, take, put, use, or clean returns no change, do not repeat the same command. Failed attempts can come from being at the wrong location, using an inexact or invalid identifier, targeting a closed or non-openable receptacle, or trying an inaccessible location.

**Why It Happens:** The same invalid action may be retried without updating the inferred state, and a failed task segment may be reissued identically instead of changing the search location, object description, or strategy.

**How To Avoid:** After a no-change observation, re-check location, inventory, exact identifiers, and object or container state. Change at least one relevant condition: move to a different reachable location, open a closed container, use the specific instance id, or switch to another strategy. After one or two identical failures, stop retrying. If a task segment fails or returns without meeting its condition, do not repeat it unchanged; broaden the search or change the approach. Before declaring blocked, ensure every plausible closed container was actually opened and inspected, not merely approached, and avoid revisiting surfaces already confirmed empty.

### G_007: Separate acquisition from operation with observable completion conditions

**Principle:** For tasks that require an object to be found and then manipulated, cleaned, heated, cooled, examined, or placed, split the task into an acquisition phase and an operation phase. The acquisition phase ends only when the target object is actually held, not merely seen and not merely because a container was opened. The operation phase ends only when the environment observation confirms the required final state, such as the object being at the destination, cleaned, heated, or cooled. Begin placement only after acquisition is confirmed by holding the target object. If a subsequent phase or handoff follows, report acquisition only after the take observation confirms holding and note any remaining operation.

**When To Apply:** When a goal requires an object to be acquired before it is used, transformed, or placed, and the object is not already held.

### G_008: Verify goal state after critical actions and stop on confirmation

**Description:** Do not declare completion or stop based on an attempted action alone. After critical actions such as take, put, clean, heat, or cool, inspect the observation for the goal predicate. Declare success only when the observation confirms the required final state; declare failure only when the observation shows an invalid or blocked action, an unreachable object, or exhaustion of plausible locations. If the placement observation already confirms the goal, treat it as terminal and do not run a redundant verification step.

**Why It Happens:** An action may be assumed successful without checking feedback, failure may be declared after a successful sequence, or an unnecessary verification step may be added after success, causing loops.

**How To Avoid:** After each critical action, compare the observation with the expected state. If the action failed, retry only after adjusting the approach; if it succeeded, stop issuing extra actions. Treat a confirming placement, cleaning, heating, or cooling observation as the terminal success condition. Do not declare completion before the final placement is confirmed; after confirmation, stop and do not send empty or inventory-only actions.

## Global — Simple pick-and-place

### T1_001: Simple pick-and-place procedure

**Principle:** For a simple pick-and-place goal, decompose the task into two ordered subtasks: first locate and take the target object, then move to the specified destination and put the object down. Keep the two steps sequential: do not begin the transfer until the object has been successfully taken, and do not release it until the destination has been reached.

**When To Apply:** When the goal is to move a single object to a specified destination and no additional state change such as cleaning, heating, cooling, or lighting is required. If the goal also requires such a state change, treat this procedure as only the transport portion and handle the extra requirement separately.

## Global — Examine with desk lamp

### T2_001: Desklamp observation: at the furniture where the desklamp is located, hold the target object and use the numbered desklamp.

**Principle:** First locate the target object and the desklamp. The desklamp is usually fixed on a furniture surface and should not be treated as a carryable item or navigation target; after observing the desklamp, go to the furniture where it is located. If the target object is not at the desklamp, first obtain it and carry it to that furniture; if the target object is already at the desklamp, confirm it is in hand before interacting. After arriving, execute the command use desklamp <id> with the instance number to trigger observation; do not use the bare name or compound syntax. Successfully turning on the desklamp is considered meeting the observation condition; do not add use/look/take/go afterward. If the target object has already been obtained at that furniture, do not repeat go to the same furniture. If use returns Nothing happens, first check whether the desklamp is listed in the current furniture observation; if not, go to another furniture where the desklamp is listed instead of retrying in place. If placing the target object repeatedly produces no change, keep holding it and directly use desklamp <id>.

**When To Apply:** When the task requires examine/look at something with/under the desklamp, an interactable desklamp exists in the environment, or observation needs to be triggered after arriving at the furniture where the desklamp is located.

### T2_002: Do not take or navigate to the desklamp.

**Description:** In failed trajectories, take desklamp, go to desklamp, or repeatedly go to the desklamp/desk often returns Nothing happens, wasting steps and possibly blocking subsequent observation; the desklamp is an interaction point fixed on furniture.

**Why It Happens:** The environment models the desklamp as a fixed light source or fixed device; only the furniture carrying the desklamp can be a navigation target, and the desklamp itself cannot be a target of take or go to.

**How To Avoid:** Do not attempt to take, move, or navigate to the desklamp. First arrive at the furniture carrying the desklamp (such as desk, sidetable, dresser, coffeetable, etc.); after arriving, directly execute the command use desklamp <id> with the number; when already at the desklamp, do not repeat go to the same location.

### T2_003: Do not use examine or compound syntax as a substitute for desklamp interaction; placing does not equal observation.

**Description:** In failed trajectories, examine X with desklamp, examine the target object, examine desklamp, examine furniture, bare-name use desklamp, use desklamp on X, use X on desklamp often return There's nothing special about X or Nothing happens and cannot substitute for the observation condition. Merely placing the target object on the desk or desklamp without triggering desklamp interaction also creates the appearance of completion without achieving the goal; if placing repeatedly produces no change, do not continue trying to place. The valid form is to use the observed numbered desklamp instance, for example use desklamp <id>.

**Why It Happens:** The environment does not support using the desklamp as an examine tool argument, nor bare names or compound syntax; examining furniture does not provide valid information, the put action itself does not trigger the observation success condition, and some furniture may refuse placement.

**How To Avoid:** After locating the target object and bringing it to the furniture where the desklamp is, use the observed numbered instance to execute use desklamp <id>. Do not use examine X with desklamp, examine target/desklamp/furniture, or compound use syntax; after invalid syntax, verify the desklamp instance name and retry rather than repeatedly examining. If put to that furniture repeatedly produces no change, keep holding it and directly use desklamp <id>.

### T2_004: When use desklamp produces no change, first verify position, instance name, and held state

**Description:** If use desklamp returns Nothing happens, it usually means you are not at the location of the desklamp, the current furniture observation does not list a desklamp, you used a bare name rather than a numbered instance, or the target object has not been obtained and interaction conditions are not met; repeating the same use/examine/look at the same location will not change state, and after one or two consecutive failures you should stop repeating to avoid loops or protection. If the target object cannot be placed on the furniture where the desklamp is, and put repeatedly produces no change, you should also not continue placing.

**Why It Happens:** Using the desklamp requires being at the same location as the furniture where the desklamp is, and satisfying conditions such as the instance name and holding the target object; wrong syntax, wrong location, or not holding the target object will not produce a state change, and an empty observation is not a retry signal. The put action itself does not trigger the observation condition.

**How To Avoid:** After failure, first verify whether the current furniture observation lists desklamp; if not, move to other furniture that lists a desklamp rather than retrying the same use. When the desklamp is present, confirm the target object has been obtained or is being held, and retry with the numbered use desklamp <id>; if there is still no change, search other locations or declare inability to complete, do not repeat the same command or fall back to examine. If put repeatedly produces no change, stop placing and keep holding it to directly use the desklamp.

### T2_005: Desklamp observation search: prioritize open surfaces, then systematically check containers

**Principle:** When searching for the target object or desklamp, prioritize checking open surfaces related to the desklamp, such as desk, sidetable, nightstand, bed, dresser, sofa, coffeetable, armchair, shelf, etc.; once a desklamp is observed, go directly to the furniture where it is and use the desklamp if needed, without continuing to traverse many drawers or unrelated containers. If the target object is not found on reasonable open surfaces, then systematically search by container type (drawer/cabinet), and return to the desklamp after finding it. Avoid repeatedly look/examine at the same location; when there is no new information, turn to other furniture or containers. 'under the desklamp' does not guarantee that the target object or desklamp is at the assumed location; when the assumed location is not visible, search other surfaces and containers, and if the desklamp is actually on other furniture, go to that furniture rather than repeatedly checking the original location.

**When To Apply:** In the desklamp observation task, when searching for the target object or desklamp, or when you have arrived at the assumed desklamp location but the target object/desklamp is not there and consecutive observations yield no new information.

## Global — Clean then place

### T3_001: Clean-then-place with verified cleaning

**Principle:** For a goal requiring a clean object to be placed, use separate stages: locate and acquire the named target; bring it to a compatible cleaning fixture, preferring a sinkbasin; clean it; verify from the observation that cleaning succeeded; then go to the destination, open it if closed, and place the object. Do not place before cleaning, and do not treat cleaning as complete without confirming evidence. If cleaning did not succeed, return to the cleaning stage before placement. If a transfer or handoff occurs after acquisition, record that cleaning is still required. Treat successful placement as the terminal condition.

**When To Apply:** When the goal is to put a clean object in or on a specified receptacle and the object is not already clean.

### T3_002: Cleaning no-effect: verify position, held object, fixture, and cleanability

**Description:** A cleaning action may produce no effect when the target is not held, the actor is not actually at a valid cleaning fixture, the current location is not a cleaning fixture, or the object is unsuitable. A sinkbasin is reliably supported in observations; alternatives such as a bathtubbasin or fridge should not be assumed equivalent. Some objects, such as towels or cloth, may not support cleaning at a sinkbasin, and repeated attempts can keep failing. Repeating identical cleaning attempts wastes steps, and trying to take another object while still holding a failed object may also produce repeated no-ops.

**Why It Happens:** The environment appears to validate that the target is held, that cleaning occurs at a compatible fixture, and that the object is cleanable; naming a fixture in a command does not substitute for being at it. Not every fixture or object supports cleaning.

**How To Avoid:** Hold the target and be at a sinkbasin before cleaning. If there is no effect, first verify that the actor is actually at the sinkbasin, then verify the held object and current location; try a different sinkbasin or confirm the object is cleanable. Treat a bathtubbasin as unverified and switch to a sinkbasin if cleaning fails. If the object type is likely non-cleanable, stop repeating cleaning; release it at a valid surface before trying another candidate, then try another cleanable candidate or report that the object is not cleanable. Do not loop on the same action.

### T3_003: Placement failure: open, verify capacity, and avoid invalid destinations

**Description:** Placement can fail when the destination container is closed, has no available space, or is not a valid receptacle. Some fixtures, such as toilets or coffeemachines, may reject placement, and repeated put/open/use attempts on a coffeemachine can return no effect. An open action may also return no effect when the container is already open or not openable.

**Why It Happens:** Containers may require opening or have capacity limits, and some fixtures are not valid placement targets. Repeating put or open without changing conditions can waste steps.

**How To Avoid:** Before placing, open a closed destination. If open returns no effect, do not retry it; treat it as already open or non-openable and proceed or reassess. Check space or availability when possible. If the destination is invalid or placement repeatedly has no effect, seek an alternative valid destination or report blocked rather than looping.

### T3_004: Use the specified object type; do not silently substitute

**Description:** Goals specify an object type. Similar alternatives such as a mug for a cup, a pan for a pot, or a butterknife for a knife should not be silently substituted. A close synonym may be used only if the exact object is unavailable and the environment or observation explicitly treats it as equivalent, or the goal permits it; otherwise continue searching or report the mismatch. If the destination already contains a similar object, still acquire, clean, and place the correct target rather than swapping.

**Why It Happens:** Generalizing categories can cause taking the wrong item and failing the task, while exact-name matching may miss an accepted synonym. Equivalence must be confirmed rather than assumed.

**How To Avoid:** Search first for the exact named type. If it is not found, do not swap in a different type by default; use only a confirmed equivalent. Confirm equivalence through explicit environmental or observational evidence or goal permission before substituting.

### T3_005: Prioritized search with bounded backtracking

**Description:** Search should prioritize plausible locations but avoid opening every remaining container indefinitely or declaring blocked prematurely. Track checked locations and avoid revisiting confirmed-empty ones. After a reasonable set of likely locations has been checked—not merely one or two when many plausible ones remain—consider unusual placement or impossibility, then reassess or report blocked. Open surfaces such as stoveburners, countertops, and dining tables must be included, not only cabinets and drawers.

**Why It Happens:** Item locations may follow regularities, but unusual placement or impossible tasks can occur. Unbounded search wastes steps and can cause timeout, while stopping too early can miss findable objects. Restricting search to closed containers misses objects placed on open surfaces.

**How To Avoid:** Prioritize likely locations by object type: food-related items in a fridge; dishes or utensils on a countertop, in a cabinet, or in a drawer; pots, kettles, or pans on stoveburners; cleaning supplies near a sinkbasin, countertop, or shelf. Keep a record of checked locations. After several likely locations fail, consider unusual placement or impossibility and reassess or report blocked rather than exhaustively opening all containers or stopping after only a couple of empty locations.

## Global — Heat then place

### T4_001: End-to-end process of heating first, then placing.

**Principle:** When the goal is to heat first and then place: locate and take the target object; if it is already in hand, proceed directly to heating; go to the microwave, open it if closed; complete heating in a way confirmed feasible by observation; keep tracking the same object instance. Heating is only an intermediate milestone; the task is complete only after the object has been placed at the destination. After heating, if the object was actually put into the microwave, take it out; if heating was completed while holding it, keep holding it and go directly to the destination. Go to the final destination, open the container if necessary, put the object in, and confirm placement. Do not treat successful heating as task completion, and do not needlessly restart already completed acquisition steps.

**When To Apply:** When the task requires first heating the object, then placing it at the specified destination.

### T4_002: Explicit commands for microwave heating and state-switch recovery

**Principle:** Before using the microwave, open it first and confirm via observation that it is open. Prefer a heating form that explicitly specifies the object and microwave, such as heat <object> with microwave <id>; generic forms such as bare use <object> or use microwave may return Nothing happens. During heating the object may be held or placed in the opened microwave; confirm the actual state according to the current observation. If held heating returns Nothing happens, you may put the object into the opened microwave and retry; if the attempt inside the microwave fails, take the object out, confirm the microwave is open, and switch to holding it to retry; you may also try holding it again after putting it in and taking it back out. After the first failure, change the object's position or held state; do not repeat the exact same failed command; if there is still no confirmation after switching, you may switch between the two states once more. Only after observing explicit heating success should you continue to the destination.

**When To Apply:** When the target object needs to be heated with the microwave, especially when the first heating attempt fails or the object is inside the microwave.

### T4_003: Do not continue placing without confirmed heating success

**Description:** The heating command may fail or return Nothing happens; treating an unconfirmed attempt as success may cause you to move and place an object that is still cold. You cannot infer heating success merely because the object is held or placed in the microwave. When observation only shows the microwave is open or the object is still held, you also cannot judge that it has been placed or heated.

**Why It Happens:** Heating can change state only when the object position and microwave state are suitable; issuing the command does not guarantee success. Without an explicit success observation, subsequent moves and placements will be based on a false premise.

**How To Avoid:** Before continuing to the next step, first verify the actual observed state (held or in-container). Continue only after an explicit heating success observation appears, such as a prompt that the object has been heated or other reliable confirmation of the hot state. If success is not confirmed, correct the object position or held state, re-execute a valid heating attempt, and verify again before moving the object.

### T4_004: After heating failure, avoid blindly substituting appliances or accepting an unheated result

**Description:** After microwave heating returns Nothing happens, switching to the stove, toaster, or another appliance without evidence may also fail or be blocked; substitution based on assumption only adds failed steps. Accepting placement of an unheated object, or replacing the hot-state goal with ordinary cooling/no-heating actions, also cannot satisfy the task requirement.

**Why It Happens:** Some appliances may not support heating the target object, some surfaces may be occupied, and the existence of an alternative appliance does not guarantee it supports that object. If placement is accepted without confirming the hot state, the task may still fail even if the action was issued.

**How To Avoid:** First correct the microwave interaction: check whether it is open, adjust whether the object is held in hand or placed inside it, and retry without repeating the exact same failed command. Use another appliance only when the current observation explicitly shows that some alternative appliance supports heating the object and is available; otherwise do not treat the stove or toaster as a blind fallback. Do not treat ordinary placement or no-heating actions as a substitute for a confirmed hot state.

### T4_005: Systematic search when the target is missing.

**Principle:** When the target object is not at the first search location, continue systematically checking other possible containers and surfaces, such as cabinets, drawers, countertops, dining tables, stoves, refrigerators, sink basins, coffee machines, side tables, etc. Maintain a record of checked locations, prioritize unchecked and already-open containers and visible surfaces, and avoid repeatedly returning to locations confirmed empty or repeatedly opening already-open containers. Do not declare the task blocked or the object nonexistent merely because the first location is empty. If several consecutive containers are empty, expand to open surfaces and other container types rather than searching drawer by drawer indefinitely; for dish-type objects, prioritize open surfaces such as dining tables, countertops, and side tables while also considering containers. After a broad search of reasonable scope, reassess rather than continuing to open every remaining container.

**When To Apply:** In the acquisition phase of a heat-then-place task, when the target object does not appear immediately or is not at the first checked location.

### T4_006: After successful held heating, do not mistakenly take the object from the microwave

**Description:** When heating succeeds while the object is held, the object remains in the held state. Subsequently attempting to take the object from the microwave may return Nothing happens, because that heating action did not put the object into the microwave; failure to take from the microwave means the object is not in the microwave, not that another take is needed.

**Why It Happens:** Heating successfully while held does not necessarily move the object into the microwave, so the object is not in the microwave to be taken. Continuing to act on the wrong location assumption produces invalid take steps.

**How To Avoid:** After successful held heating, confirm via inventory or held state that the object is still in hand, then go to the destination. Unless the object was actually placed into the microwave, do not issue a take-from-microwave action; if take-from-microwave returns Nothing happens, check the held state rather than repeating the take.

### T4_007: Avoid extra intermediate placements between heating and the destination

**Description:** Inserting an extra countertop or other intermediate placement between heating and the final destination adds unnecessary actions and may cause object tracking or final placement to fail.

**Why It Happens:** The task may be over-decomposed, introducing an intermediate placement step even though the goal only requires moving the heated object to the final destination. Intermediate placement changes the object's location and adds state that must be tracked.

**How To Avoid:** After heating, pick up or keep holding the object, go directly to the final destination, and place it there. Add such intermediate placement steps only when the environment explicitly requires them.

## Global — Cool then place

### T5_001: Cool the target and verify state before destination placement

**Principle:** Treat environment feedback as authority. Acquire the exact target and check current holdings so an already-held object is not re-taken. Go to the cooling location, open it if needed, and while holding the target there use the available explicit cooling interaction for the target and cooling container. If no explicit cooling action exists, use the available cooling interaction. Do not substitute placing the object inside and immediately re-taking it for cooling. Wait for a cooled-state confirmation; containment, brief placement, or a round-trip alone is not confirmation. After cooling succeeds while holding, proceed directly to the destination without an extra take-from-container step. Open the destination if closed, place the object, and confirm placement. Cooling is an intermediate checkpoint; do not signal completion at that point because final placement is also required.

**When To Apply:** When the goal requires an object to be brought to a cooled state and then placed at a specified destination.

### T5_002: Do not confuse containment or a brief cooling attempt with confirmed cooled state

**Description:** An object found in or briefly placed inside a cooling container may not be in the required cooled state; cooling must be performed or verified explicitly before transport to the destination.

**Why It Happens:** Location or containment can be mistaken for temperature state, and a round-trip may be assumed sufficient. The environment may change the relevant state only through an explicit cooling interaction.

**How To Avoid:** After opening the cooling container and holding the target, use the available cooling interaction and wait for cooled-state confirmation. Do not immediately retrieve an object just placed inside and treat it as cooled. If no confirmation appears, do not assume success; retry or report the unresolved state through the available feedback channel.

### T5_003: Search likely locations first, then reassess feasibility

**Principle:** Search high-probability locations first: the cooling container, countertops, stove burners, dining table, cabinets, drawers, and shelves. Prefer visible surfaces before closed-container sweeps; open containers as needed and track visited locations. Reaching a closed container is not inspection: its contents remain unverified until opened. If the target is absent from the first expected location, continue a bounded search of plausible surfaces and containers rather than declaring failure. When found on an accessible surface, take it and proceed. If a reasonable broad search finds nothing, reassess feasibility or absence instead of checking unrelated receptacles. Do not repeat an identical broad search after obvious receptacles are exhausted; raise uncertainty when feasibility is doubtful.

**When To Apply:** When the target object is not immediately visible or is missing from its expected location, and many storage receptacles exist.

### T5_004: Complete both cooling and final placement checkpoints

**Description:** Placing the object without cooling, stopping after opening the cooling container, or cooling without final placement leaves the goal incomplete. The goal requires both a cooled object and placement at the specified destination.

**Why It Happens:** The goal can be misread as simple placement, or cooling can be treated as the whole mission. Declaring completion after a partial step, after repeated cooling failures, or when the cooled state was never confirmed also causes failure.

**How To Avoid:** Treat cooling and final placement as separate checkpoints. Include an explicit cooling step before placement when a cooled object is required, then continue to the destination and place the object. Do not declare success until both the cooled state and destination placement have been confirmed. If cooling repeatedly fails, do not signal completion on placement alone.

## Global — Place two objects

### T6_001: Two-item sequential placement with per-item verification and placement tracking

**Principle:** Treat a two-item placement goal as two search-and-place cycles. For each cycle: locate and take one target object, navigate to the destination, open it if closed, place the object, and verify the placement from the observation before starting the next cycle. Track how many items are placed and which item was already placed; never take an already-placed item again. If a second take fails while an object is held, place the held object at the destination before returning for the second. If both instances are visible on the same surface or receptacle, place the first and then return to that same location for the second. If the final destination is temporarily unavailable, use only a safe recoverable holding location when necessary, then move both objects to the final destination afterward. Treat each placement as a checkpoint, not task completion.

**When To Apply:** When the goal requires placing two instances of the same object type at one target location and only one object can be carried at a time.

### T6_002: Systematic broad search with checked-location tracking

**Principle:** When target objects are not immediately visible, search broadly rather than checking only one receptacle type. Inspect visible open surfaces such as counters, tables, shelves, sofas, and similar surfaces first, then check closed containers such as cabinets and drawers, opening them before inspecting or taking from inside. Continue across multiple location types until the required number of instances is found or a checked-location record shows no remaining unchecked likely locations. If both target instances are visible on the same surface, take one, place it, then return to that same surface for the second rather than wandering to unrelated containers. Treat an unreachable or no-change navigation target as unavailable and move to another candidate. Reassess feasibility after likely locations are exhausted, but do not conclude the task is blocked prematurely.

**When To Apply:** When one or both target objects are not visible and must be located in the environment.

### T6_003: Single-item carry limit blocks a second take or movement

**Description:** Attempts to take a second object, or sometimes to move to another location, while already holding an object can return no effect. This blocks progress in two-item placement if the held object is not released first. A failed second take while an object is held should be diagnosed as the one-item carry limit, not as the second object being absent.

**Why It Happens:** The environment commonly allows carrying only one object at a time, so take or movement actions may be rejected while inventory is occupied.

**How To Avoid:** Before taking the second object or moving to search elsewhere, put the held object into the final destination or into a safe recoverable temporary location. Confirm the hands are empty, then continue. When a take fails while holding an object, attribute it to occupied inventory and place the held object first rather than concluding the target is missing.

### T6_004: Verify destination and placement before continuing

**Description:** A put action can produce no effect if issued before reaching the destination receptacle, or it can fail without the failure being noticed. Continuing to search for the second item after an unconfirmed first placement can leave the goal unsatisfied. When a put returns no change, first verify that the actor is actually at the destination before concluding the receptacle rejects placement; a subsequent go-to-destination followed by a retried put often succeeds. If the destination repeatedly rejects placement after the location cause is ruled out, reassess whether it is valid and report blocked rather than looping or abandoning the held object.

**Why It Happens:** Placement requires being at the target container, and a successful put must be verified from the observation; otherwise the first item may still be held or not placed. Misattributing a location failure to receptacle type can lead to wrong alternative-destination actions, while some named destinations may be invalid or unreachable.

**How To Avoid:** Navigate to the destination before placing. After each put, inspect the observation to confirm success. If the put did not succeed, verify the current location, move to the target if needed, and retry before starting the next search or placement cycle. Do not switch to an alternative receptacle until the destination-location cause has been ruled out; if repeated rejection continues, reassess validity and report blocked.

### T6_005: Open containers from the container location before access

**Description:** Attempting to put an object into, or take an object from, a closed cabinet, drawer, or similar container may produce no effect. Issuing open on an already-open container may also return no change and should not be retried. Issuing open on a container while standing at its parent furniture may return no change; the actor must navigate to the container itself first.

**Why It Happens:** The environment requires the container to be open before its contents can be accessed or modified, reports no change when opening an already-open container, and validates open actions against the actor's current location being the container rather than its parent furniture.

**How To Avoid:** Navigate to the container itself, then open it with the appropriate open action. If it is already open, or if opening returns no change, proceed to take or place rather than retrying open. After opening, verify access before taking or placing. Do not issue open on a container from its parent furniture.

### T6_006: Examine-style actions do not provide usable information

**Description:** Using an examine-style action on objects or locations is not supported and returns no useful information.

**Why It Happens:** The available interaction set is limited to navigation, taking, putting, opening, and inventory-style operations; examining is not an effective substitute.

**How To Avoid:** Inspect a location by navigating to the receptacle and observing its contents. Pick up visible target objects with a take action from that receptacle.

### T6_007: Avoid unsuitable temporary containers for held objects

**Description:** Placing an object into a non-target or unsuitable container such as a garbage can can make retrieval impossible or cause the overall two-item placement to fail.

**Why It Happens:** Some containers may not accept objects cleanly, may change object state, or may not allow reliable retrieval; temporary storage is only safe if the object can be taken back.

**How To Avoid:** Prefer placing the first object directly into the final destination. If temporary holding is unavoidable, choose an open, stable, recoverable surface or container and avoid garbage cans or other likely irreversible containers.

### T6_008: Prevent budget exhaustion through checked-location and feasibility discipline

**Description:** After several containers have been opened and no target found, repeatedly revisiting locations already confirmed empty, re-taking an already-placed instance, repeating a no-change navigation, or trying yet another receptacle after many failed put attempts can exhaust the action budget and cause failure. A held object whose put attempts fail across many receptacles may indicate an unplaceable object or an infeasible goal rather than a wrong receptacle. Do not assert a specific unseen location contains the target or that a failed action was transient without observed evidence. Do not declare failure before all plausible open surfaces and closed containers have actually been opened and inspected.

**Why It Happens:** Searching without tracking checked locations and placed instances leads to redundant actions, while unchecked opened containers or visible surfaces may still contain the target. A no-change navigation indicates the target location is unreachable or invalid, so retrying it cannot help. Speculation about unseen contents or transient failures drives further wasted steps, and premature failure declaration leaves plausible locations unexamined.

**How To Avoid:** Maintain a list of checked locations and placed instances. Prioritize unchecked opened containers and visible surfaces; take a target directly if it is visible. Avoid revisiting a location confirmed to have no target or re-taking an already-placed object unless new evidence suggests otherwise. After one no-change navigation, choose a different unchecked location. Base advice on observed state rather than asserting unseen contents or transient failures. Before declaring blocked, ensure all plausible open surfaces and closed containers were actually opened and inspected. If every put attempt fails across many receptacles, stop suggesting new receptacles and reassess the held object's exact identifier and whether the destination accepts placement, considering the object unplaceable or the goal infeasible.

### T6_009: Signal completion only after actual progress and avoid re-taking placed items

**Description:** Repeatedly declaring a subtask complete without executing the required next action can trigger a loop guard and terminate the episode before the two items are placed. Re-taking an already-placed item and re-placing it at a different instance of the destination can also trigger a guard.

**Why It Happens:** The current state may be misread as satisfying the completion condition even though the actual goal or subgoal is unfinished, causing repeated signals instead of progress; alternatively, the destination instance may be confused, leading to re-taking a placed item.

**How To Avoid:** Signal completion only after the corresponding subgoal is actually achieved, such as an object being taken or placed. After signaling, continue with the necessary next action and avoid repeating the same completion signal without new progress. Track which destination instance is the goal; once an item is placed at the target, do not re-take it, and search for a second instance instead.

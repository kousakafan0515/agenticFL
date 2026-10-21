# English reference: B1_skillbank.json

Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.

## Planner — General

### skill_001: Locate target before acting

**Principle:** For any task, first locate the target object by checking open surfaces and likely locations before attempting to take or manipulate it.

**When To Apply:** All tasks where the target object's location is not initially known.

### skill_002: Failure Lesson

**Description:** In failed episodes, the planner often searched many closed drawers or cabinets before checking open surfaces where the target object was actually visible. This wastes steps and can lead to plan failure when the object is on an open surface.

**Why It Happens:** The initial plan treats 'find the object' as an unconstrained search and does not prioritize open, directly observable locations over closed containers.

**How To Avoid:** When locating the target object, first inspect open surfaces and visible locations (tables, dressers, shelves, countertops, sofas, beds, etc.) before opening closed containers. Only open closed containers if the object is not found on any open surface.

### skill_003: Failure Lesson

**Description:** In failed episodes, the planner repeatedly attempted to take the target object from locations where it was not present, and sometimes concluded the object was unavailable without systematically checking all plausible open surfaces. This led to plan failure even though the object may have been present elsewhere.

**Why It Happens:** The search strategy does not maintain a systematic list of candidate locations and may prematurely stop or repeat failed locations.

**How To Avoid:** After a failed take attempt, mark that location as checked and move to a new unchecked plausible location. Continue until all plausible open surfaces and relevant containers have been checked before declaring the object unavailable.

### skill_004: Failure Lesson

**Description:** Plans often fail because the agent assumes an action succeeded without checking the observation, then proceeds with subsequent steps based on a false state.

**Why It Happens:** The planner may not include verification steps or may ignore failed action feedback.

**How To Avoid:** After critical actions (take, put, clean, heat, cool), check the observation to confirm success. If the action failed, retry or adjust the plan before continuing.

## Planner — Simple pick-and-place

### skill_005: Two-step simple pick-and-place plan

**Principle:** For simple pick-and-place goals, decompose the task into exactly two ordered subtasks: (S1) find and take the target object, then (S2) put the target object at the specified destination.

**When To Apply:** When the goal is a simple pick-and-place instruction such as 'put a/an/some <object> in/on <destination>' and no additional state change (cleaning, heating, cooling, etc.) is required.

## Planner — Examine with desk lamp

### skill_006: Desklamp observation: first locate and turn on the desklamp, then take the target object.

**Principle:** In the desklamp observation task, first find and turn on the desklamp, then acquire the object to be observed, and finally execute examine/look.

**When To Apply:** The goal is examine/look at X under/with the desklamp, and a usable desklamp exists in the environment.

### skill_007: Failure Lesson

**Description:** Multiple failed trajectories show that a plan to take desklamp first causes subsequent take/examine to fail or prevents completion of the observation.

**Why It Happens:** desklamp may not be carryable or may need to remain in place as the observation light source; taking the desklamp first will break the subsequent examine/look conditions.

**How To Avoid:** Prefer to find and turn on the desklamp near the target object's location; if the target object must be moved, bring the target object to the desklamp instead of taking the desklamp away first.

### skill_008: Failure Lesson

**Description:** Multiple failed trajectories repeatedly open and close drawers or move blindly when the target object has not been found, resulting in plan_failed.

**Why It Happens:** The target object may be in containers such as drawers or cabinets; attempting to take the object without a systematic search will fail.

**How To Avoid:** First systematically search for the target object by container type (drawer/cabinet), and after finding it, execute take and examine/look.

### skill_009: Failure Lesson

**Description:** Some trajectories put the target object on the desk or desklamp but did not execute examine/look, resulting in plan_completed_without_environment_win.

**Why It Happens:** The task goal is observation, not placement; the put action does not trigger the observation success condition.

**How To Avoid:** After the target object and the desklamp are in the same place, you must execute examine X or look at X under the desklamp.

## Planner — Clean then place

### skill_010: Standard three-step plan for cleaning then placing.

**Principle:** For the "clean then place" task, the initial plan should be decomposed into three ordered subtasks: S1 find and pick up the target item; S2 clean the item in the sinkbasin; S3 put the cleaned item into or on the target container or surface.

**When To Apply:** When the goal is "put a clean X in/on Y" or "clean some X and put it in/on Y".

### skill_011: Failure Lesson

**Description:** Some items (such as towel, cloth) will not succeed when performing the clean action on sinkbasin, causing the plan to fail.

**Why It Happens:** Not all items in the environment support the clean action, or the target item may not be the cleanable item required by the task.

**How To Avoid:** When making a plan, prioritize common cleanable items (such as cup, bowl, plate, knife, pot, pan, kettle, soapbar, lettuce, tomato, potato, egg, dishsponge, ladle, mug, etc.); if the clean action fails, try other candidate items or check whether the item is cleanable.

### skill_012: Failure Lesson

**Description:** When the target container (such as drawer, cabinet, coffeemachine) is full, closed, or does not exist, direct placement will fail.

**Why It Happens:** Containers in the environment have capacity limits or need to be opened first; some target locations may have no available free space.

**How To Avoid:** Before placing, first check whether the target container is open and has free space; if the target container is unavailable, find an alternative container or first empty/open the target container.

### skill_013: Failure Lesson

**Description:** When looking for the target item, prioritize checking common locations such as fridge, countertop, cabinet, drawer, shelf, and avoid wasting steps in irrelevant locations.

**Why It Happens:** Item distribution in the environment follows patterns, and common locations are more likely to contain the target item; blind searching can exhaust steps or cause the plan to fail.

**How To Avoid:** Choose priority search locations based on item type: for food items, prioritize fridge; for tableware, prioritize countertop, cabinet, drawer; for cleaning supplies, prioritize sinkbasin, countertop, shelf.

## Planner — Heat then place

### skill_014: Heat-then-place plan with explicit microwave open/close and heat verification

**Principle:** For heat-then-place goals, decompose into: (1) locate and take the target object, (2) go to microwave, (3) open microwave, (4) put object in microwave, (5) close microwave if open, (6) heat object with microwave, (7) verify the object is hot, (8) take the hot object, (9) go to destination, (10) put the hot object at destination.

**When To Apply:** Any task requiring heating an object and then placing it at a destination.

### skill_015: Failure Lesson

**Description:** Heating actions fail when the object is still in inventory or when the microwave is closed. The object must be placed inside an open microwave before the heat action can succeed.

**Why It Happens:** The environment requires the object to be inside the appliance and the appliance to be open/closed appropriately before heating.

**How To Avoid:** After taking the object, go to the microwave, open it, put the object in, close it if needed, then heat. Do not call heat while holding the object.

### skill_016: Failure Lesson

**Description:** Plans often fail because the heat action did not actually make the object hot, yet the agent proceeds to take and place it. The agent should confirm the object is hot (e.g., via observation or successful heat action) before moving it.

**Why It Happens:** The heat action may fail silently or require multiple attempts; without verification, the agent may place a cold object and fail the goal.

**How To Avoid:** After heating, check the object state or ensure the heat action returned success before taking it. If not hot, repeat the heat action with the object properly placed in the microwave.

### skill_017: Failure Lesson

**Description:** Some plans include an extra step of placing the heated object on a countertop before moving it to the final destination. This adds unnecessary actions and can cause the plan to fail if the object is not properly tracked.

**Why It Happens:** The planner may over-decompose the task, inserting an intermediate placement that is not required by the goal.

**How To Avoid:** After heating, take the object directly to the final destination and place it there. Do not insert intermediate placements unless required by the environment.

## Planner — Cool then place

### skill_018: Cooling requires explicit fridge placement and retrieval

**Principle:** For cooling tasks, after acquiring the target object, explicitly place it in the fridge, then take it back out before moving to the final destination.

**When To Apply:** When the goal requires an object to be cooled before being placed in a final location.

### skill_019: Failure Lesson

**Description:** Plans that omit the cooling step and directly place the object in the final location fail to satisfy the goal condition.

**Why It Happens:** The planner may treat the goal as a simple placement task and overlook the required intermediate cooling state.

**How To Avoid:** Always include an explicit cooling step in the plan when the goal specifies a cool object.

### skill_020: Failure Lesson

**Description:** When the target object is not found in the first few likely locations, the planner may enter a long search loop across many cabinets and drawers, wasting steps and failing the task.

**Why It Happens:** The planner lacks a fallback strategy and continues searching without reconsidering the plan or using alternative object sources.

**How To Avoid:** Limit search to a few high-probability locations; if the object is not found, consider whether the goal can be satisfied with a similar object or whether the plan needs to be revised.

### skill_021: Failure Lesson

**Description:** Plans that assume an object taken from the fridge is already cool and skip the explicit cooling step may fail if the object was not actually cooled or if the goal requires a specific cooling action.

**Why It Happens:** The planner may conflate the object's initial location with the required cooled state.

**How To Avoid:** Always perform the cooling action explicitly, even if the object is found in the fridge, unless the goal explicitly allows using an already-cool object.

## Planner — Place two objects

### skill_022: Sequential two-item placement

**Principle:** For two-item placement tasks, process one item at a time: locate and take the first item, place it at the target, then locate and take the second item, and place it at the target.

**When To Apply:** When the goal requires placing two instances of the same object type at a single target location.

### skill_023: Failure Lesson

**Description:** In some failed trajectories, the agent attempted to place the first item at the target but the placement did not succeed, yet the agent continued searching for the second item. This led to plan completion without the goal being satisfied.

**Why It Happens:** The agent may assume a put action succeeded without checking the observation, or may attempt to put an item at a target that is not reachable or not in the current location.

**How To Avoid:** After each put action, check the observation to confirm the item was placed. If the put action fails, navigate to the target location and retry before proceeding to find the second item.

## Executor — General

### skill_001: Search likely receptacles before opening every drawer

**Principle:** When the target object is not visible, first visit surfaces and open containers that commonly hold the target object, then take the object and place it at the goal location.

**When To Apply:** When the target object is not visible at the start and the goal is to put it in/on a specified receptacle.

### skill_002: Do not use examine or open on non-container surfaces

**Principle:** In ALFWorld, 'examine' is not a valid action, and 'open' only works on openable containers such as drawers, cabinets, safes, fridges, and microwaves. Using these actions on desks, tables, sofas, beds, shelves, or garbagecans produces 'Nothing happens' and wastes steps.

**When To Apply:** When searching for an object and considering whether to examine or open a surface or non-openable receptacle.

### skill_003: Do not attempt to take an object from a location without first navigating there

**Principle:** The 'take <object> from <receptacle>' action only succeeds when the agent is at that receptacle and the object is present. Attempting to take from a distant or unvisited location yields 'Nothing happens'.

**When To Apply:** When the target object has not yet been observed at the current location.

### skill_004: Avoid repeated failed navigation to the same unreachable location

**Principle:** If 'go to <location>' returns 'Nothing happens' repeatedly for the same location, stop retrying it and continue searching elsewhere. Repeatedly targeting an unreachable or invalid location can exhaust the step budget and cause plan failure.

**When To Apply:** When a navigation action to a specific location has already failed once or twice.

### skill_005: Use exact ALFWorld action forms

**Principle:** Use 'go to <location>' for navigation, 'take <object> from <receptacle>' for retrieval, 'put <object> in/on <receptacle>' for placement, and 'open <container>' before accessing closed containers.

**When To Apply:** Throughout all ALFWorld tasks.

## Executor — Examine with desk lamp

### skill_006: Desklamp observation task: first locate and carry the target object, then go to the desklamp's location and use the desklamp

**Principle:** In the 'desklamp observation' task, first search for and obtain the target object, then go to the desklamp's location, and finally use the desklamp to complete the observation.

**When To Apply:** When the task requires examine/look at an object with/under the desklamp.

### skill_007: Failure Lesson

**Description:** desklamp is usually fixed on a desk or side table; take desklamp will fail and return Nothing happens.

**Why It Happens:** In ALFWorld, the desklamp is a fixed light source, not a carryable item.

**How To Avoid:** Do not attempt take desklamp; go to the desklamp's location and execute the command use desklamp to turn it on.

### skill_008: Failure Lesson

**Description:** After already being at the desklamp location, repeating go to desklamp or go to desk returns Nothing happens, wasting steps.

**Why It Happens:** The desklamp is not a navigable location, and desk may also be unable to be navigated to again because it has already been reached.

**How To Avoid:** After reaching the surface where the desklamp is, directly execute the command use desklamp; if you need to observe an object, first ensure the target object is carried or is near the desklamp.

### skill_009: Failure Lesson

**Description:** When searching for the target object, if the target object is more likely to appear on surfaces such as desktops, side tables, beds, etc., do not prioritize or repeatedly traverse a large number of drawers.

**Why It Happens:** Drawer search is costly, and in many desklamp observation tasks the target object is on open surfaces.

**How To Avoid:** First check surfaces related to the desklamp, such as desktops, side tables, nightstands, etc.; check drawers only when not found in reasonable locations.

## Executor — Clean then place

### skill_010: Clean-then-place sequence for cleaning followed by placing

**Principle:** For clean-and-place goals, first locate and take the target object, then navigate to a sinkbasin, clean the held object with the sinkbasin, then navigate to the destination receptacle and put the object there.

**When To Apply:** When the goal is to put a clean object in/on a target receptacle and the object is not already clean.

### skill_011: Open closed destination receptacles before placing

**Principle:** If the destination receptacle is closed, open it before attempting to put the clean object inside.

**When To Apply:** When the target destination is a closed cabinet, drawer, fridge, microwave, or similar container.

### skill_012: Do not clean non-cleanable objects such as towels

**Principle:** Some objects, such as towels, cannot be cleaned with a sinkbasin; repeated clean attempts fail and waste steps.

**When To Apply:** When the target object is a towel or another object that does not support the clean action.

### skill_013: Do not assume coffeemachine accepts placed mugs

**Principle:** A coffeemachine may not be a valid placement receptacle for a clean mug; put attempts can fail even when holding the correct object.

**When To Apply:** When the goal destination is a coffeemachine and the put action returns no effect.

## Executor — Heat then place

### skill_014: Failure Lesson

**Description:** Across many failed trajectories, the agent placed the object in the microwave and then attempted to heat it, resulting in 'Nothing happens.' In successful trajectories, the agent took the object from the microwave (or held it) and then issued the heat command, which succeeded.

**Why It Happens:** The ALFWorld heat action expects the object to be held by the agent, not merely inside the appliance.

**How To Avoid:** After opening the microwave, take the object into inventory, then issue 'heat <object> with microwave 1'.

### skill_015: Failure Lesson

**Description:** Many failed trajectories show the agent repeatedly trying 'use microwave 1' and 'heat <object> with microwave 1' without changing the object's location, leading to plan failure. Successful trajectories show that taking the object out and then heating it works.

**Why It Happens:** The environment does not allow heating an object that is inside the microwave; the object must be held.

**How To Avoid:** After a failed heating attempt, take the object from the microwave, then issue the heat command while holding it.

### skill_016: Successful heating and placement sequence

**Principle:** To heat an object and place it in a target receptacle: find and take the object, go to the microwave, open it, take the object (if needed), heat it while holding it, then go to the target and put it there.

**When To Apply:** When the goal is to heat an object and put it in a specified location.

## Executor — Cool then place

### skill_017: Cooling requires placing the object in the fridge and then retrieving it

**Principle:** For cooling tasks, first place the target object into the fridge, then take it out before moving it to the final destination.

**When To Apply:** When the goal is to cool an object and then place it in a cabinet, countertop, microwave, garbagecan, diningtable, sidetable, or coffeemachine.

### skill_018: Failure Lesson

**Description:** If the object is not already in the fridge, placing it in the fridge and then taking it out is required; directly taking an object from the fridge without first putting it there does not satisfy the cooling subtask.

**Why It Happens:** The agent may assume that any object taken from the fridge is already cool, but the task requires the agent to perform the cooling action.

**How To Avoid:** Always put the target object into the fridge before taking it out, even if the object was originally found elsewhere.

### skill_019: Failure Lesson

**Description:** If the target object is not found in the fridge, countertops, or dining table, do not search every cabinet and drawer; instead, reconsider the object name or task assumptions.

**Why It Happens:** The agent may continue searching all containers, wasting steps and failing to complete the task.

**How To Avoid:** After checking a few likely locations, if the object is still missing, re-examine the goal or consider that the object may not be present in the environment.

## Executor — Place two objects

### skill_020: Sequential two-item placement with single-item carry

**Principle:** For two-item placement tasks, locate and take the first target object, carry it to the destination receptacle, place it, then search for and place the second target object.

**When To Apply:** When the goal is to put two instances of the same object type into a specified receptacle and the agent can carry only one object at a time.

### skill_021: Search likely receptacles for target objects

**Principle:** When the target object is not visible, search common receptacles such as countertops, tables, shelves, cabinets, drawers, sofas, and toilets, opening closed containers before checking inside.

**When To Apply:** When the target object type is not immediately visible in the current location and the task requires finding one or more instances.

### skill_022: Failure Lesson

**Description:** The 'examine' action is not valid in this environment and produces 'Nothing happens.' without providing useful information.

**Why It Happens:** The agent may attempt to use 'examine' as a way to inspect objects or locations, but the environment only supports navigation, taking, putting, opening, and inventory actions.

**How To Avoid:** Use 'go to <receptacle>' to navigate to a location and observe its contents, then use 'take <object> from <receptacle>' to pick up items.

### skill_023: Failure Lesson

**Description:** Attempting to put an object into a closed container or take from a closed container results in 'Nothing happens.' The container must be opened first.

**Why It Happens:** The environment requires containers to be open before their contents can be accessed or modified.

**How To Avoid:** Before putting an object into a cabinet, drawer, or similar container, ensure it is open by using 'open <container>'. If it is already open, proceed with the put action.

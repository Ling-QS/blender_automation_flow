# Automation Flow

Node-based Blender automation flow prototype for:

- Capturing, storing, parsing, and applying modifier properties through unified `Property Definition` / `Property Package` payloads.
- Building object and collection lists for bake isolation workflows.
- Triggering `GN Bake Task` and physics bake tasks from an Automation Flow tree.
- Running simple linear flow execution with precheck, dry-run support, and log output.

## Current Node Groups

- Flow: `Start`, `End`, `Run Task Plan`, `Wait For Task`, `Delay Wait`, `Reload After Task`
- Object / Collection: `Collection List`, `Collection Expand`, `Object List`, `Scene Object List`
- Bake / Dependency: `GN Bake Task`, `Physics Bake Settings`, `Physics Bake Task`, `Evaluate Object Dependencies`
- Property Package: `Modifier Property Data`, `Create Property Package`, `Store Property Package`, `Apply Object Properties`, `Apply Property Package`, `Parse Property Package`, `Filter Property Package`, `Merge Property Packages`
- Utility: float / integer / boolean / vector input and math nodes

## Property Package Notes

- `Modifier Property Data`, `Object Display Property Data`, and `Object Transform Property Data` each output both `Property Definition` and `Property Assignment`.
- `Create Property Package` builds packages from `Object List + one or more Property Assignment` inputs.
- Set each property field source to `Current` to capture scene state, or keep it on `Value` to build a target package from explicit values.
- `Store Property Package` can either persist an incoming package or output a previously stored one.
- `Apply Object Properties` applies a package to an explicit `Object List`.
- `Apply Property Package` restores directly from the package's embedded definition and object scope.

## Test Notes

- Existing `.blend` test trees may need a one-time node refresh after socket layout changes.
- Workspace helper scripts for current validation:
  - `tools/validate_property_package_cleanup.py`
  - `tools/refresh_property_package_nodes.py`

## Quick Validation Flow

1. Create an `Automation Flow` tree in the Node Editor.
2. Add and connect:
   - `Start`
   - `Modifier Property Data` for capture
   - `Modifier Property Data` for target
   - `Create Property Package`
   - `Store Property Package`
   - `Create Property Package`
   - `Apply Object Properties`
   - `End`
3. Set the capture property data fields to `Current`, then connect its `Property Assignment` output plus `Object List` into the first `Create Property Package`.
4. Set the target property data fields to `Value`, then connect its `Property Assignment` output plus `Object List` into the second `Create Property Package`.
5. Connect the captured package into `Store Property Package`, then connect the target package into `Apply Object Properties`. Connect the target property data `Property Definition` output into `Apply Object Properties`.
6. Run the flow from the sidebar panel.

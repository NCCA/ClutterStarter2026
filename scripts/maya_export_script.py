from pathlib import Path

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as OpenMayaUI
import maya.cmds as cmds
import maya.OpenMaya as OM1
import pymel.core as pm

# ---------------------------------------------------------------------------
# Viewport helpers
# ---------------------------------------------------------------------------


def disable_grid() -> None:
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel) == "modelPanel":
        cmds.modelEditor(panel, edit=True, grid=False)


def enable_grid() -> None:
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel) == "modelPanel":
        cmds.modelEditor(panel, edit=True, grid=True)


def save_screenshots(
    path: str,
    width: int,
    height: int,
    base_name: str,
    frame_all: bool = True,
    view_manip: bool = False,
    persp: bool = True,
    top: bool = True,
    side: bool = True,
    front: bool = True,
) -> None:
    """Capture viewport screenshots for each requested view and write them to disk."""
    views = {
        "Persp": ("cmds.viewSet(p=True, fit=True)", persp),
        "Top": ("cmds.viewSet(t=True, fit=True)", top),
        "Side": ("cmds.viewSet(s=True, fit=True)", side),
        "Front": ("cmds.viewSet(f=True, fit=True)", front),
    }

    for name, (command, is_active) in views.items():
        if is_active:
            try:
                exec(command)
                view = OpenMayaUI.M3dView.active3dView()
                panel = cmds.getPanel(visiblePanels=True)
                cmds.setFocus(panel[0])
                disable_grid()

                if frame_all:
                    pm.viewFit()

                image = om.MImage()
                view.refresh()
                cmds.viewManip(v=view_manip)
                view.readColorBuffer(image, True)
                image.resize(width, height, preserveAspectRatio=True)
                png_path = f"{path}/{base_name}{name}.png"
                image.writeToFile(png_path, outputFormat="png")
            except Exception as e:
                print(f"Failed to save screenshot for {name} view: {e}")
                enable_grid()


# ---------------------------------------------------------------------------
# DAG helpers
# ---------------------------------------------------------------------------


def get_dag_node(name: str) -> tuple[om.MFnDagNode, om.MDagPath]:
    """Return an MFnDagNode and MDagPath for the named object."""
    sel = om.MSelectionList()
    sel.add(name)
    dag_path = sel.getDagPath(0)
    return om.MFnDagNode(dag_path), dag_path


def collect_meshes(dag_path: om.MDagPath, meshes: list[str]) -> None:
    """
    Recursively walk the DAG hierarchy under *dag_path* and collect the full
    path strings of all mesh transform nodes.
    """
    fn_dag = om.MFnDagNode(dag_path)

    for i in range(fn_dag.childCount()):
        child_obj = fn_dag.child(i)
        child_path = om.MDagPath(dag_path)
        child_path.push(child_obj)

        if child_obj.hasFn(om.MFn.kMesh):
            # Collect the transform parent, not the shape itself.
            transform_path = om.MDagPath(child_path)
            transform_path.pop()
            meshes.append(transform_path.fullPathName())
        elif child_obj.hasFn(om.MFn.kTransform):
            collect_meshes(child_path, meshes)


# ---------------------------------------------------------------------------
# Normalise & export
# ---------------------------------------------------------------------------


def normalize_selected_group(group_name: str) -> str | None:
    """
    Duplicate all meshes from the currently selected group into a new group,
    then centre it at the world origin and scale it to unit size.

    Returns the name of the new group, or None on failure.
    """
    selection = cmds.ls(selection=True, long=True)

    if not selection:
        om.MGlobal.displayError("Nothing selected. Please select a group.")
        return None

    root_name = selection[0]

    if not cmds.objectType(root_name, isType="transform"):
        om.MGlobal.displayError(
            f"Selected object is not a transform/group: {root_name}"
        )
        return None

    # 1. Collect mesh transforms.
    _, root_dag_path = get_dag_node(root_name)
    mesh_transforms: list[str] = []
    collect_meshes(root_dag_path, mesh_transforms)

    if not mesh_transforms:
        om.MGlobal.displayError("No meshes found inside the selected group.")
        return None

    om.MGlobal.displayInfo(
        f"Found {len(mesh_transforms)} mesh transform(s) in '{root_name}'."
    )

    # 2. Create a new base group.
    base_group = cmds.group(empty=True, name=group_name, world=True)

    # 3. Duplicate each mesh and parent it into the new group.
    for mesh_tf in mesh_transforms:
        dupe = cmds.duplicate(mesh_tf, renameChildren=True)[0]
        cmds.parent(dupe, base_group)
        cmds.makeIdentity(dupe, apply=True, rotate=True, translate=False, scale=False)
        om.MGlobal.displayInfo(f"  Duplicated '{mesh_tf}' -> '{dupe}'")

    # 4. Compute the world-space bounding box.
    x_min, y_min, z_min, x_max, y_max, z_max = cmds.exactWorldBoundingBox(base_group)
    center_x = (x_min + x_max) / 2.0
    center_y = (y_min + y_max) / 2.0
    center_z = (z_min + z_max) / 2.0
    max_size = max(x_max - x_min, y_max - y_min, z_max - z_min)

    if max_size < 1e-6:
        om.MGlobal.displayError(
            "Bounding box is (near) zero in size — cannot scale to unit size."
        )
        cmds.delete(base_group)
        return None

    # 5. Centre at world origin and scale to unit size.
    sel = om.MSelectionList()
    sel.add(base_group)
    fn_transform = om.MFnTransform(sel.getDagPath(0))
    fn_transform.setTranslation(
        om.MVector(-center_x, -center_y, -center_z), om.MSpace.kWorld
    )
    uniform_scale = 1.0 / max_size
    fn_transform.setScale([uniform_scale, uniform_scale, uniform_scale])

    om.MGlobal.displayInfo(
        f"'{base_group}' moved to origin and scaled by {uniform_scale:.6f}."
    )

    cmds.select(base_group, replace=True)
    return base_group


def export_mesh(root_name: str, export_root: str) -> None:
    """
    Normalise a single group, save screenshots and an OBJ, then clean up.

    Args:
        root_name:   Maya node name of the group to export.
        export_root: Filesystem root under which a per-mesh subfolder is created.
    """
    # Extract the last part after the final colon (e.g., "Hook_7" from "|Kitchen_set:Hook_7")
    if ":" in root_name:
        safe_name = root_name.split(":")[-1]
    else:
        safe_name = root_name.lstrip("|").replace("|", "_")
    export_dir = Path(export_root) / safe_name
    export_dir.mkdir(exist_ok=True, parents=True)

    cmds.select(root_name, replace=True)
    new_group = normalize_selected_group("NCCA_Export")

    if new_group is None:
        om.MGlobal.displayError(f"Skipping '{root_name}': normalisation failed.")
        return

    try:
        cmds.select(new_group)
        cmds.hide(all=True)
        cmds.showHidden(new_group)
        cmds.select(new_group)
        save_screenshots(str(export_dir), 250, 250, safe_name)
        cmds.file(
            str(export_dir / f"{safe_name}.obj"),
            force=True,
            type="OBJexport",
            exportSelected=True,
        )
        om.MGlobal.displayInfo(f"Exported '{safe_name}' to '{export_dir}'.")
    finally:
        cmds.delete(new_group)
        cmds.showHidden(all=True)


def export_all_selected(export_root: str) -> None:
    """
    Export every selected group as a separate normalised OBJ with screenshots.

    Args:
        export_root: Root directory under which per-mesh subfolders are created.
    """
    selection = cmds.ls(selection=True, long=True)

    if not selection:
        om.MGlobal.displayError("Nothing selected. Please select one or more groups.")
        return

    om.MGlobal.displayInfo(f"Exporting {len(selection)} selected item(s)...")

    interrupter = OM1.MComputation()
    interrupter.beginComputation()

    try:
        for item in selection:
            if interrupter.isInterruptRequested():
                om.MGlobal.displayWarning("Export interrupted by user.")
                break

            if not cmds.objectType(item, isType="transform"):
                om.MGlobal.displayWarning(f"Skipping '{item}': not a transform/group.")
                continue

            om.MGlobal.displayInfo(f"Processing '{item}'...")
            export_mesh(item, export_root)
    finally:
        interrupter.endComputation()
        cmds.select(clear=True)

    om.MGlobal.displayInfo("Export complete.")


export_root = "/home/jmacey/Desktop/25-26/ClutterStarter/ExportedMeshes"
export_all_selected(export_root)

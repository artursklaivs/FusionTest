import adsk.core
import adsk.fusion
import traceback

CMD_ID = 'kitchenCabinetGeneratorCmd'
CMD_NAME = 'Ģenerēt virtuves skapīti'
CMD_DESCRIPTION = 'Izveido skapīti (priekšskats) pēc platuma, augstuma, dziļuma un plauktu skaita.'
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'BoxCommand'
BACK_PANEL_THICKNESS_MM = 3.0
PARTS_LIBRARY_NAME = 'KitchenCabinetPartsLibrary'

handlers = []


def _mm(value: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByString(f'{value} mm')


def _translation_matrix(x: float, y: float, z: float) -> adsk.core.Matrix3D:
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(x, y, z)
    return matrix


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            inputs.addValueInput('width', 'Platums', 'mm', _mm(600))
            inputs.addValueInput('height', 'Augstums', 'mm', _mm(720))
            inputs.addValueInput('depth', 'Dziļums', 'mm', _mm(320))
            inputs.addIntegerSpinnerCommandInput('shelves', 'Plauktu skaits', 0, 12, 1, 2)
            inputs.addValueInput('thickness', 'Korpusa biezums', 'mm', _mm(18))

            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            handlers.append(on_execute)
        except Exception:
            _show_error('Neizdevās inicializēt komandu.')


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                _show_error('Aktīvais dokuments nav Fusion Design.')
                return

            root_comp = design.rootComponent
            cmd = args.firingEvent.sender
            inputs = cmd.commandInputs

            width = inputs.itemById('width').value
            height = inputs.itemById('height').value
            depth = inputs.itemById('depth').value
            shelves = inputs.itemById('shelves').value
            thickness = inputs.itemById('thickness').value
            back_thickness = BACK_PANEL_THICKNESS_MM / 10.0  # Fusion iekšēji lieto cm

            min_size = thickness * 2.0 + 0.1
            if width <= min_size or height <= min_size or depth <= back_thickness:
                _show_error('Pārāk mazi izmēri izvēlētajam korpusa biezumam.')
                return

            _build_cabinet(root_comp, width, height, depth, thickness, back_thickness, shelves)
        except Exception:
            _show_error('Kļūda izveidojot skapīti.')


def _find_child_component(parent: adsk.fusion.Component, name: str):
    for occ in parent.occurrences:
        if occ.component.name == name:
            return occ.component
    return None


def _get_or_create_parts_library(root_comp: adsk.fusion.Component) -> adsk.fusion.Component:
    existing = _find_child_component(root_comp, PARTS_LIBRARY_NAME)
    if existing:
        return existing

    occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.isLightBulbOn = False
    library_comp = occ.component
    library_comp.name = PARTS_LIBRARY_NAME
    return library_comp


def _create_part_geometry(part_comp: adsk.fusion.Component, width: float, height: float, depth: float):
    sketches = part_comp.sketches
    sketch = sketches.add(part_comp.xYConstructionPlane)
    lines = sketch.sketchCurves.sketchLines
    p1 = adsk.core.Point3D.create(0, 0, 0)
    p2 = adsk.core.Point3D.create(width, height, 0)
    lines.addTwoPointRectangle(p1, p2)

    profile = sketch.profiles.item(0)
    extrudes = part_comp.features.extrudeFeatures
    ext_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(depth))
    extrudes.add(ext_input)


def _get_or_create_part_component(library_comp: adsk.fusion.Component,
                                  part_code: str,
                                  width: float,
                                  height: float,
                                  depth: float) -> adsk.fusion.Component:
    key = f'{part_code}_{int(width*10)}x{int(height*10)}x{int(depth*10)}'

    existing = _find_child_component(library_comp, key)
    if existing:
        return existing

    occ = library_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    part_comp = occ.component
    part_comp.name = key
    _create_part_geometry(part_comp, width, height, depth)
    return part_comp


def _place_part_occurrence(target_comp: adsk.fusion.Component,
                           part_comp: adsk.fusion.Component,
                           x: float,
                           y: float,
                           z: float):
    # Fusion API dažās versijās Occurrence.name ir read-only, tāpēc neuzstādam to manuāli.
    target_comp.occurrences.addExistingComponent(part_comp, _translation_matrix(x, y, z))


def _build_cabinet(root_comp: adsk.fusion.Component,
                   width: float,
                   height: float,
                   depth: float,
                   thickness: float,
                   back_thickness: float,
                   shelf_count: int):
    library_comp = _get_or_create_parts_library(root_comp)

    cabinet_occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    cabinet_comp = cabinet_occ.component
    cabinet_comp.name = f'Skapītis_{int(width*10)}x{int(height*10)}x{int(depth*10)}'

    inner_width = width - 2 * thickness
    inner_height = height - 2 * thickness

    side_part = _get_or_create_part_component(library_comp, 'SANS', thickness, height, depth)
    horizontal_part = _get_or_create_part_component(library_comp, 'HORIZONTAL', inner_width, thickness, depth)
    back_part = _get_or_create_part_component(library_comp, 'AIZMUGURE3', width, height, back_thickness)

    # Priekšskats: Z=0 ir priekšējā mala, skapītis iet uz aizmuguri (negatīvs Z).
    _place_part_occurrence(cabinet_comp, side_part, 0, 0, -depth)
    _place_part_occurrence(cabinet_comp, side_part, width - thickness, 0, -depth)

    _place_part_occurrence(cabinet_comp, horizontal_part, thickness, 0, -depth)
    _place_part_occurrence(cabinet_comp, horizontal_part, thickness, height - thickness, -depth)

    if shelf_count > 0:
        gap = (inner_height - shelf_count * thickness) / (shelf_count + 1)
        for i in range(shelf_count):
            y = thickness + gap * (i + 1) + thickness * i
            _place_part_occurrence(cabinet_comp, horizontal_part, thickness, y, -depth)

    _place_part_occurrence(cabinet_comp, back_part, 0, 0, -depth)


def _show_error(message: str):
    app = adsk.core.Application.get()
    ui = app.userInterface if app else None
    detail = traceback.format_exc()
    if ui:
        ui.messageBox(f'{message}\n\n{detail}')


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESCRIPTION)

    on_created = CommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    handlers.append(on_created)

    panel = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(PANEL_ID)
    control = panel.controls.itemById(CMD_ID)
    if not control:
        control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)
    control.isPromoted = True


def stop(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    panel = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(PANEL_ID)
    control = panel.controls.itemById(CMD_ID)
    if control:
        control.deleteMe()

    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()

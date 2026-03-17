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

handlers = []


def _mm(value: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByString(f'{value} mm')


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


def _create_board(parent_comp: adsk.fusion.Component,
                  name: str,
                  x: float,
                  y: float,
                  width: float,
                  height: float,
                  z: float,
                  depth: float):
    """Izveido plātni no priekšskata (X-Y), ekstrūzija notiek pa Z asi (dziļumā)."""
    sketches = parent_comp.sketches
    xy_plane = parent_comp.xYConstructionPlane
    sketch = sketches.add(xy_plane)
    rect_lines = sketch.sketchCurves.sketchLines

    p1 = adsk.core.Point3D.create(x, y, 0)
    p2 = adsk.core.Point3D.create(x + width, y + height, 0)
    rect_lines.addTwoPointRectangle(p1, p2)

    prof = sketch.profiles.item(0)
    extrudes = parent_comp.features.extrudeFeatures
    ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_input.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(z))
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(depth))
    ext = extrudes.add(ext_input)
    ext.bodies.item(0).name = name


def _build_cabinet(root_comp: adsk.fusion.Component,
                   width: float,
                   height: float,
                   depth: float,
                   thickness: float,
                   back_thickness: float,
                   shelf_count: int):
    occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = f'Skapītis_{int(width*10)}x{int(height*10)}x{int(depth*10)}'

    inner_width = width - 2 * thickness
    inner_height = height - 2 * thickness

    # Priekšskats: Z=0 ir priekšējā mala, skapītis iet uz aizmuguri (negatīvs Z).
    _create_board(comp, 'Kreisais sāns', 0, 0, thickness, height, 0, -depth)
    _create_board(comp, 'Labais sāns', width - thickness, 0, thickness, height, 0, -depth)

    _create_board(comp, 'Apakša', thickness, 0, inner_width, thickness, 0, -depth)
    _create_board(comp, 'Augša', thickness, height - thickness, inner_width, thickness, 0, -depth)

    if shelf_count > 0:
        gap = (inner_height - shelf_count * thickness) / (shelf_count + 1)
        for i in range(shelf_count):
            y = thickness + gap * (i + 1) + thickness * i
            _create_board(comp, f'Plaukts_{i + 1}', thickness, y, inner_width, thickness, 0, -depth)

    # Aizmugure 3 mm bieza pie pašas aizmugures malas.
    _create_board(comp, 'Aizmugure_3mm', 0, 0, width, height, -depth, back_thickness)


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

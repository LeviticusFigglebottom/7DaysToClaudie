class_name RenderCaps
## What the running renderer can do that the game's shaders lean on.


## False on the Compatibility renderer (OpenGL): it keeps instance uniforms in one uniform buffer
## the driver caps at 4096 slots, which a streamed world overflows, so the shaders declare material
## uniforms there instead (TD-325). Setting a per-instance value still allocates the instance's
## slots, so callers skip it.
static func instance_uniforms() -> bool:
	return RenderingServer.get_current_rendering_method() != "gl_compatibility"


## False on the Compatibility renderer: it has no volumetric fog, and compiling a `fog` shader there
## is an engine error, so the ground-fog volume is never made (the depth fog still carries it).
static func fog_volumes() -> bool:
	return RenderingServer.get_current_rendering_method() != "gl_compatibility"

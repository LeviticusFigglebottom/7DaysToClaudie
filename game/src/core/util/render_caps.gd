class_name RenderCaps
## What the running renderer can do that the game's shaders lean on.


## False on the Compatibility renderer (OpenGL): it keeps instance uniforms in one uniform buffer
## the driver caps at 4096 slots, which a streamed world overflows, so the shaders declare material
## uniforms there instead (TD-325). Setting a per-instance value still allocates the instance's
## slots, so callers skip it.
static func instance_uniforms() -> bool:
	return RenderingServer.get_current_rendering_method() != "gl_compatibility"

class_name ImageStats
extends RefCounted
## Numbers for QA pictures (the shot tools print them beside each file).


## The picture's mean luma (Rec. 709 on its sRGB values, every 4th pixel each way): how dark a view
## reads, 0..1.
static func mean_luma(img: Image) -> float:
	var total: float = 0.0
	var n: int = 0
	for y: int in range(0, img.get_height(), 4):
		for x: int in range(0, img.get_width(), 4):
			var c: Color = img.get_pixel(x, y)
			total += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
			n += 1
	return total / maxf(1.0, n)

import type { Transform } from '@gltf-transform/core';
/** Options for the {@link vertexColorSpace} function. */
export interface ColorSpaceOptions {
    /** Input color space of vertex colors, to be converted to "srgb-linear". Required. */
    inputColorSpace: 'srgb' | 'srgb-linear';
}
/**
 * Vertex color color space correction. The glTF format requires vertex colors to be stored
 * in Linear Rec. 709 D65 color space, and this function provides a way to correct vertex
 * colors that are (incorrectly) stored in sRGB.
 *
 * Example:
 *
 * ```typescript
 * import { vertexColorSpace } from '@gltf-transform/functions';
 *
 * await document.transform(
 *   vertexColorSpace({ inputColorSpace: 'srgb' })
 * );
 * ```
 *
 * @category Transforms
 */
export declare function vertexColorSpace(options: ColorSpaceOptions): Transform;

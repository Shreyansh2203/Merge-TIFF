export const MAX_STEM_LENGTH = 40;
export const MAX_OUTPUT_STEM_LENGTH = 120;

const UNSAFE_FILENAME_CHARS = /[\u0000-\u001f\u007f/\\:*?"<>|]/g;
const OUTPUT_SUFFIX = '_merged.tif';

export function buildOutputName(names) {
  const stems = names
    .map((name) =>
      name
        .replace(UNSAFE_FILENAME_CHARS, '')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\.[^.]+$/, '')
        .slice(0, MAX_STEM_LENGTH)
        .trim()
    )
    .filter(Boolean);

  if (stems.length === 0) {
    return 'merged_document.tif';
  }

  const summary =
    stems.length <= 4
      ? stems.join('_')
      : `${stems.slice(0, 3).join('_')}_and_${stems.length - 3}_more`;

  return `${summary.slice(0, MAX_OUTPUT_STEM_LENGTH)}${OUTPUT_SUFFIX}`;
}

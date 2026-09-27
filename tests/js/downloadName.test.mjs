import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  MAX_OUTPUT_STEM_LENGTH,
  MAX_STEM_LENGTH,
  buildOutputName
} from '../../src/lib/downloadName.mjs';

const OUTPUT_SUFFIX = '_merged.tif';

// Every name Windows refuses to create a file for, and every DOS device name a
// download could be mistaken for.
const RESERVED = [
  'CON', 'PRN', 'AUX', 'NUL',
  'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
  'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
];

const CASES = [
  { label: 'a single page', names: ['page1.tif'], expected: 'page1_merged.tif' },
  { label: 'four pages join with underscores', names: ['a.tif', 'b.tif', 'c.tif', 'd.tif'], expected: 'a_b_c_d_merged.tif' },
  { label: 'five pages summarise as a count', names: ['a.tif', 'b.tif', 'c.tif', 'd.tif', 'e.tif'], expected: 'a_b_c_and_2_more_merged.tif' },
  { label: 'nothing selected', names: [], expected: 'merged_document.tif' },
  { label: 'blank names', names: ['', '   ', '\t\n'], expected: 'merged_document.tif' },
  { label: 'names that sanitise to nothing', names: ['///', '<<<>>>', '|||'], expected: 'merged_document.tif' },
  { label: 'a name of only dots', names: ['...'], expected: '..._merged.tif' },
  { label: 'control characters', names: ['\u0000\u001f\u007fpage.tif'], expected: 'page_merged.tif' },
  { label: 'path separators and drive letters', names: ['C:\\Users\\me\\scan.tif'], expected: 'CUsersmescan_merged.tif' },
  { label: 'reserved characters', names: ['a:b*c?d"e<f>g|h.tif'], expected: 'abcdefgh_merged.tif' },
  { label: 'surrounding and repeated whitespace', names: ['  spaced   out  .tif'], expected: 'spaced out_merged.tif' },
  { label: 'a long name is truncated', names: [`${'a'.repeat(200)}.tif`], expected: `${'a'.repeat(MAX_STEM_LENGTH)}_merged.tif` },
  { label: 'a reserved device name', names: ['CON.tif'], expected: 'CON_merged.tif' },
  { label: 'a reserved device name, lowercase', names: ['com9'], expected: 'com9_merged.tif' },
  { label: 'a name that is only an extension', names: ['.tif'], expected: 'merged_document.tif' },
  { label: 'a name that only looks reserved', names: ['CONSOLE.tif'], expected: 'CONSOLE_merged.tif' },
  { label: 'mixed reserved and ordinary names', names: ['NUL.tif', 'LPT9.tif', 'page.tif'], expected: 'NUL_LPT9_page_merged.tif' }
];

describe('buildOutputName', () => {
  for (const { label, names, expected } of CASES) {
    it(`returns the expected name for ${label}`, () => {
      assert.equal(buildOutputName(names), expected);
    });
  }

  for (const { label, names } of CASES) {
    it(`never produces an unusable name for ${label}`, () => {
      const name = buildOutputName(names);
      const stem = name.slice(0, name.length - '.tif'.length);

      assert.notEqual(name, '');
      assert.notEqual(stem.trim(), '');
      assert.equal(RESERVED.includes(stem.toUpperCase()), false);
      assert.ok(
        name.length <= MAX_OUTPUT_STEM_LENGTH + OUTPUT_SUFFIX.length,
        `${name.length} characters is over the bound`
      );
    });
  }

  it('keeps the bound when every name is long', () => {
    const name = buildOutputName(
      Array.from({ length: 20 }, (_unused, index) =>
        `${String(index).repeat(MAX_STEM_LENGTH)}.tif`
      )
    );

    assert.ok(name.length <= MAX_OUTPUT_STEM_LENGTH + OUTPUT_SUFFIX.length);
  });
});

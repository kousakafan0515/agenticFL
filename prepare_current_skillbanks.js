/* Build compact current SkillBank views from the copied raw update records. */
const fs = require('fs');
const path = require('path');
const root = __dirname;
const sources = [
  ['client_a_current_skillbank.json', 'client_a_mixed_deepseek_flash_v1_24_8k', false],
  ['client_b_current_skillbank.json', 'client_b_mixed_deepseek_flash_v1_24_8k', false],
  ['client_c_current_skillbank_reviewed_v1.json', 'client_c_mixed_deepseek_flash_v1_24_8k', true],
];
for (const [output, directory, reviewed] of sources) {
  const base = path.join(root, 'skill_generation_results', directory);
  let payload;
  if (reviewed) {
    const source = JSON.parse(fs.readFileSync(path.join(base, 'skillbanks_reviewed_v1.json'), 'utf8'));
    payload = { source_client: 'C', review_status: 'reviewed_v1', ...source };
  } else {
    const source = JSON.parse(fs.readFileSync(path.join(base, 'updates.json'), 'utf8'));
    payload = { source_client: output.includes('client_a') ? 'A' : 'B', source_generation_result: `skill_generation_results/${directory}/updates.json`, active_skillbanks: source.skillbanks };
  }
  fs.writeFileSync(path.join(root, 'current_skillbanks', output), JSON.stringify(payload, null, 2), 'utf8');
}

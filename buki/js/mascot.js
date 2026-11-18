// Буки — маскот приложения. Круглый персонаж с листком-хохолком в форме буквы «Б».
// mood: happy | cheer | think | care

export function mascot(mood = 'happy', size = 96) {
  const mouths = {
    happy: '<path d="M40 66 Q50 75 60 66" stroke="var(--ink)" stroke-width="3.5" fill="none" stroke-linecap="round"/>',
    cheer: '<path d="M38 63 Q50 80 62 63 Z" fill="var(--ink)"/><path d="M44 70 Q50 74 56 70" stroke="#ff8fa3" stroke-width="3" fill="none" stroke-linecap="round"/>',
    think: '<path d="M43 69 L57 67" stroke="var(--ink)" stroke-width="3.5" stroke-linecap="round"/>',
    care: '<path d="M41 68 Q50 73 59 68" stroke="var(--ink)" stroke-width="3.5" fill="none" stroke-linecap="round"/>',
  };
  const eyesY = mood === 'think' ? 49 : 51;
  const pupilDX = mood === 'think' ? 2 : 0;
  const arms = mood === 'cheer'
    ? '<path d="M18 62 Q6 46 12 36" stroke="var(--mascot-dark)" stroke-width="7" fill="none" stroke-linecap="round"/><path d="M82 62 Q94 46 88 36" stroke="var(--mascot-dark)" stroke-width="7" fill="none" stroke-linecap="round"/>'
    : '<path d="M17 66 Q10 72 14 80" stroke="var(--mascot-dark)" stroke-width="7" fill="none" stroke-linecap="round"/><path d="M83 66 Q90 72 86 80" stroke="var(--mascot-dark)" stroke-width="7" fill="none" stroke-linecap="round"/>';
  const brows = mood === 'care'
    ? '<path d="M31 38 L41 41" stroke="var(--ink)" stroke-width="3" stroke-linecap="round"/><path d="M69 38 L59 41" stroke="var(--ink)" stroke-width="3" stroke-linecap="round"/>'
    : '';
  return `<svg class="mascot mascot-${mood}" width="${size}" height="${size}" viewBox="0 0 100 100" aria-hidden="true">
    <ellipse cx="50" cy="95" rx="28" ry="4" fill="var(--shadow)"/>
    <path d="M50 22 C50 10 58 4 66 6 C64 13 58 18 50 22 Z" fill="var(--leaf)"/>
    <path d="M50 22 C47 15 41 12 36 14" stroke="var(--leaf)" stroke-width="3" fill="none" stroke-linecap="round"/>
    ${arms}
    <path d="M50 20 C76 20 86 40 86 60 C86 80 70 92 50 92 C30 92 14 80 14 60 C14 40 24 20 50 20 Z" fill="var(--mascot)"/>
    <path d="M50 26 C70 26 79 41 79 58 C79 64 77 68 74 71 C70 54 60 44 50 44 C40 44 30 54 26 71 C23 68 21 64 21 58 C21 41 30 26 50 26 Z" fill="var(--mascot-light)" opacity=".55"/>
    <ellipse cx="50" cy="72" rx="20" ry="15" fill="var(--belly)"/>
    <circle cx="38" cy="${eyesY}" r="9" fill="#fff"/><circle cx="62" cy="${eyesY}" r="9" fill="#fff"/>
    <circle cx="${39 + pupilDX}" cy="${eyesY + 1}" r="5" fill="var(--ink)"/><circle cx="${63 + pupilDX}" cy="${eyesY + 1}" r="5" fill="var(--ink)"/>
    <circle cx="${41 + pupilDX}" cy="${eyesY - 1}" r="1.8" fill="#fff"/><circle cx="${65 + pupilDX}" cy="${eyesY - 1}" r="1.8" fill="#fff"/>
    ${brows}
    <circle cx="28" cy="62" r="5" fill="#ff8fa3" opacity=".55"/><circle cx="72" cy="62" r="5" fill="#ff8fa3" opacity=".55"/>
    ${mouths[mood] || mouths.happy}
  </svg>`;
}

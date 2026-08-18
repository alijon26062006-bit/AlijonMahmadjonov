/** QR-код ссылки — рисуем сами, без обращения к чужому сервису.

    Нужен тем, кто открыл сайт с компьютера: набирать адрес бота на телефоне
    руками неудобно, а навести камеру — секунда.
*/
import qr from 'qrcode-generator';
import { useMemo } from 'react';

export default function Qr({ value, size = 168 }: { value: string; size?: number }) {
  const path = useMemo(() => {
    // 0 — размер подбирается сам под длину ссылки; M — средняя коррекция
    // ошибок: её хватает, а модулей получается меньше, значит крупнее клетка
    const code = qr(0, 'M');
    code.addData(value);
    code.make();
    const n = code.getModuleCount();
    let d = '';
    for (let row = 0; row < n; row += 1) {
      for (let col = 0; col < n; col += 1) {
        if (code.isDark(row, col)) d += `M${col} ${row}h1v1h-1z`;
      }
    }
    return { d, n };
  }, [value]);

  return (
    <svg viewBox={`0 0 ${path.n} ${path.n}`} width={size} height={size}
         role="img" aria-label="QR-код ссылки на бота"
         shapeRendering="crispEdges">
      <rect width={path.n} height={path.n} fill="#ffffff" />
      <path d={path.d} fill="#0a0a0a" />
    </svg>
  );
}

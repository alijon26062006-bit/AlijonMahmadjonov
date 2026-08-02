<?php
/**
 * CodeTJ — санҷиши файлҳои дарс (seed/*.json).
 * Танҳо барои созанда. Ба ҳостинг бор кардан лозим нест.
 *
 * Иҷро: php validate_seed.php
 */

$dir = __DIR__ . '/seed';
$files = glob($dir . '/*.json');
if (!$files) {
    echo "Дар папкаи seed/ файли JSON нест.\n";
    exit(1);
}
sort($files);

$allowedTags = array('h3', 'p', 'ul', 'ol', 'li', 'b', 'code', 'pre', 'strong', 'em', 'br');
$errors = 0;
$total = 0;

foreach ($files as $file) {
    $raw = file_get_contents($file);
    $data = json_decode($raw, true);
    echo "\n=== " . basename($file) . " ===\n";
    if (!is_array($data)) {
        echo "  ХАТО: JSON вайрон аст — " . json_last_error_msg() . "\n";
        $errors++;
        continue;
    }
    foreach ($data as $i => $L) {
        $tag = 'дарс #' . ($i + 1);
        $problems = array();

        foreach (array('course', 'num', 'title_tj', 'title_ru', 'theory_tj', 'theory_ru',
                       'example_code', 'task_text_tj', 'task_text_ru', 'task_criteria') as $k) {
            if (!isset($L[$k]) || (is_string($L[$k]) && trim($L[$k]) === '')) {
                $problems[] = "майдони «$k» холӣ";
            }
        }
        if (isset($L['course']) && !in_array($L['course'], array('html', 'css', 'js', 'full'), true)) {
            $problems[] = 'course нодуруст: ' . $L['course'];
        }
        if (isset($L['num']) && ((int)$L['num'] < 1 || (int)$L['num'] > 50)) {
            $problems[] = 'num аз ҳудуд берун: ' . $L['num'];
        }
        $tag = ($L['course'] ?? '?') . ' #' . ($L['num'] ?? '?');

        // ҳаҷми назария
        foreach (array('theory_tj', 'theory_ru') as $k) {
            if (isset($L[$k])) {
                $words = str_word_count(strip_tags($L[$k]), 0, 'абвгдеёжзийклмнопрстуфхцчшщъыьэюяӣӯҳқғҷАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯӢӮҲҚҒҶ');
                if ($words < 250) {
                    $problems[] = "$k хеле кӯтоҳ ($words калима)";
                }
            }
        }

        // тегҳои иҷозатдодашуда
        foreach (array('theory_tj', 'theory_ru', 'task_text_tj', 'task_text_ru') as $k) {
            if (!isset($L[$k])) {
                continue;
            }
            if (preg_match('/<\s*(script|style|iframe|object|embed|form|link|meta)\b/i', $L[$k], $m)) {
                $problems[] = "$k теги хатарнок дорад: <" . $m[1] . '>';
            }
            if (preg_match('/\son[a-z]+\s*=/i', $L[$k])) {
                $problems[] = "$k атрибути on...= дорад";
            }
            preg_match_all('/<\s*\/?\s*([a-z][a-z0-9]*)/i', $L[$k], $mm);
            foreach (array_unique($mm[1]) as $tg) {
                if (!in_array(strtolower($tg), $allowedTags, true)) {
                    $problems[] = "$k теги ғайричашмдошт: <" . $tg . '>';
                }
            }
        }

        // саволҳо
        if (!isset($L['questions']) || !is_array($L['questions'])) {
            $problems[] = 'саволҳо нестанд';
        } else {
            $qc = count($L['questions']);
            if ($qc !== 5) {
                $problems[] = "саволҳо $qc-то (бояд 5)";
            }
            $corrects = array();
            foreach ($L['questions'] as $qi => $q) {
                $n = $qi + 1;
                foreach (array('q_tj', 'q_ru', 'explain_tj', 'explain_ru') as $k) {
                    if (!isset($q[$k]) || trim((string)$q[$k]) === '') {
                        $problems[] = "савол $n: «$k» холӣ";
                    }
                }
                $ot = isset($q['options_tj']) && is_array($q['options_tj']) ? $q['options_tj'] : array();
                $or = isset($q['options_ru']) && is_array($q['options_ru']) ? $q['options_ru'] : array();
                if (count($ot) !== 4) {
                    $problems[] = "савол $n: вариантҳои тоҷикӣ " . count($ot) . '-то (бояд 4)';
                }
                if (count($or) !== 4) {
                    $problems[] = "савол $n: вариантҳои русӣ " . count($or) . '-то (бояд 4)';
                }
                if (count(array_unique($ot)) !== count($ot)) {
                    $problems[] = "савол $n: вариантҳои такрорӣ";
                }
                $c = isset($q['correct']) ? (int)$q['correct'] : -1;
                if ($c < 0 || $c > 3) {
                    $problems[] = "савол $n: correct=$c нодуруст";
                }
                $corrects[] = $c;
            }
            if (count($corrects) === 5 && count(array_unique($corrects)) === 1) {
                $problems[] = 'ҳамаи ҷавобҳои дуруст як хеланд (correct=' . $corrects[0] . ') — омехта кунед';
            }
        }

        $total++;
        if ($problems) {
            $errors++;
            echo "  [ХАТО] $tag — " . (isset($L['title_tj']) ? $L['title_tj'] : '?') . "\n";
            foreach ($problems as $pr) {
                echo "      - $pr\n";
            }
        } else {
            $w = str_word_count(strip_tags($L['theory_tj']), 0, 'абвгдеёжзийклмнопрстуфхцчшщъыьэюяӣӯҳқғҷ');
            echo "  [хуб]  $tag — " . $L['title_tj'] . " ({$w} калима)\n";
        }
    }
}

echo "\n----------------------------------------\n";
echo "Ҳамагӣ: $total дарс, хато: $errors\n";
exit($errors > 0 ? 1 : 0);

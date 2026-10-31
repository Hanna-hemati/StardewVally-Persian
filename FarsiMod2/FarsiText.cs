using System.Text;

namespace FarsiMod2;

/// <summary>
/// Runtime text engine for Persian text that was not shaped offline.
///
/// Strings coming from translation assets are already in visual order with
/// contextual (joined) forms, so they skip this engine. Player-entered text
/// (chat messages, farm names, etc.) still starts in logical order, which the
/// game's LTR-only renderer draws backwards and disconnected. This class turns
/// logical Persian into the visual form the game expects:
///
/// 1. contextual shaping  - each letter is swapped for the isolated / final /
///                            initial / medial presentation form it needs;
/// 2. bidi reordering     - lines are reversed run-by-run so RTL text draws
///                            correctly, with embedded Latin words, digits,
///                            game tokens and brackets kept intact;
/// 3. idempotence         - text that already contains presentation forms is
///                            never transformed twice.
/// </summary>
public static class FarsiText
{
    /// <summary>Arabic letter in the base block (excludes Arabic-Indic digits).</summary>
    private static bool IsArabicBaseLetter(char c)
    {
        if (IsArabicDigit(c)) return false;
        return (c >= '\u0621' && c <= '\u063A')
            || (c >= '\u0641' && c <= '\u064A')
            || c == '\u0640'
            || (c >= '\u066E' && c <= '\u06FF');
    }

    /// <summary>True when the text still contains logical (unshaped) Arabic letters.</summary>
    public static bool ContainsBasePersian(string? text)
    {
        if (string.IsNullOrEmpty(text)) return false;
        foreach (char c in text)
        {
            if (IsArabicBaseLetter(c)) return true;
        }
        return false;
    }

    /// <summary>True when the string has any Arabic-script character (base or presentation).</summary>
    public static bool ContainsAnyRtl(string? text)
    {
        if (string.IsNullOrEmpty(text)) return false;
        foreach (char c in text)
        {
            if (IsRtl(c)) return true;
        }
        return false;
    }

    private static bool IsArabicDigit(char c) =>
        (c >= '\u0660' && c <= '\u0669') || (c >= '\u06F0' && c <= '\u06F9');


    public static bool IsRtl(char c)
    {
        if (IsArabicDigit(c)) return false;
        return (c >= '\u0600' && c <= '\u06FF')
            || (c >= '\u0750' && c <= '\u077F')
            || (c >= '\u08A0' && c <= '\u08FF')
            || (c >= '\uFB50' && c <= '\uFDFF')
            || (c >= '\uFE70' && c <= '\uFEFF');
    }

    private static bool IsLtr(char c)
    {
        if (c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9') return true;
        if (c >= '\u00C0' && c <= '\u024F') return true;
        if (c >= '\u0370' && c <= '\u052F') return true;
        if (c >= '\u06F0' && c <= '\u06F9') return true;
        if (c >= '\uE000' && c < '\uE100') return true; // masked game tokens
        return false;
    }

    private static char Mirror(char c) => c switch
    {
        '(' => ')', ')' => '(',
        '[' => ']', ']' => '[',
        '{' => '}', '}' => '{',
        '<' => '>', '>' => '<',
        '«' => '»', '»' => '«',
        '‹' => '›', '›' => '‹',
        '“' => '”', '”' => '“',
        '‘' => '’', '’' => '‘',
        _ => c,
    };

    // ------------------------------------------------------------------ shaping

    // <isolated, final, initial, medial> presentation codepoints (U+FE70..FEFC plus
    // FB5x-FBFF Persian letters). 0 means "this joining form does not exist".
    private static readonly Dictionary<char, int[]> Forms = new()
    {
        ['ء'] = new[] { 0xFE80, 0, 0, 0 },
        ['آ'] = new[] { 0xFE81, 0xFE82, 0, 0 },
        ['أ'] = new[] { 0xFE83, 0xFE84, 0, 0 },
        ['ؤ'] = new[] { 0xFE85, 0xFE86, 0, 0 },
        ['إ'] = new[] { 0xFE87, 0xFE88, 0, 0 },
        ['ئ'] = new[] { 0xFE89, 0xFE8A, 0xFE8B, 0xFE8C },
        ['ا'] = new[] { 0xFE8D, 0xFE8E, 0, 0 },
        ['ب'] = new[] { 0xFE8F, 0xFE90, 0xFE91, 0xFE92 },
        ['ة'] = new[] { 0xFE93, 0xFE94, 0, 0 },
        ['ت'] = new[] { 0xFE95, 0xFE96, 0xFE97, 0xFE98 },
        ['ث'] = new[] { 0xFE99, 0xFE9A, 0xFE9B, 0xFE9C },
        ['ج'] = new[] { 0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0 },
        ['ح'] = new[] { 0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4 },
        ['خ'] = new[] { 0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8 },
        ['د'] = new[] { 0xFEA9, 0xFEAA, 0, 0 },
        ['ذ'] = new[] { 0xFEAB, 0xFEAC, 0, 0 },
        ['ر'] = new[] { 0xFEAD, 0xFEAE, 0, 0 },
        ['ز'] = new[] { 0xFEAF, 0xFEB0, 0, 0 },
        ['س'] = new[] { 0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4 },
        ['ش'] = new[] { 0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8 },
        ['ص'] = new[] { 0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC },
        ['ض'] = new[] { 0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0 },
        ['ط'] = new[] { 0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4 },
        ['ظ'] = new[] { 0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8 },
        ['ع'] = new[] { 0xFEC9, 0xFECA, 0xFECB, 0xFECC },
        ['غ'] = new[] { 0xFECD, 0xFECE, 0xFECF, 0xFED0 },
        ['ف'] = new[] { 0xFED1, 0xFED2, 0xFED3, 0xFED4 },
        ['ق'] = new[] { 0xFED5, 0xFED6, 0xFED7, 0xFED8 },
        ['ك'] = new[] { 0xFED9, 0xFEDA, 0xFEDB, 0xFEDC },
        ['ک'] = new[] { 0xFB8E, 0xFB8F, 0xFB90, 0xFB91 },
        ['ل'] = new[] { 0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0 },
        ['م'] = new[] { 0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4 },
        ['ن'] = new[] { 0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8 },
        ['ه'] = new[] { 0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC },
        ['و'] = new[] { 0xFEED, 0xFEEE, 0, 0 },
        ['ى'] = new[] { 0xFEEF, 0xFEF0, 0, 0 },
        ['ی'] = new[] { 0xFBFC, 0xFBFD, 0xFBFE, 0xFBFF },
        ['گ'] = new[] { 0xFB92, 0xFB93, 0xFB94, 0xFB95 },
        ['چ'] = new[] { 0xFB7A, 0xFB7B, 0xFB7C, 0xFB7D },
        ['پ'] = new[] { 0xFB56, 0xFB57, 0xFB58, 0xFB59 },
        ['ژ'] = new[] { 0xFB8A, 0xFB8B, 0, 0 },
        ['ٹ'] = new[] { 0xFB66, 0xFB67, 0xFB68, 0xFB69 },
    };

    /// <summary>This letter connects to the letter before it (a final form exists).</summary>
    private static bool JoinsLeft(char c) => Forms.TryGetValue(c, out int[]? f) && f is not null && f[1] != 0;

    /// <summary>This letter connects to the letter after it (an initial form exists).</summary>
    private static bool JoinsRight(char c) => Forms.TryGetValue(c, out int[]? f) && f is not null && f[2] != 0;

    /// <summary>Replace every base Persian letter with its contextual presentation form.</summary>
    public static string Shape(string text)
    {
        var sb = new StringBuilder(text.Length);

        // ZWNJ blocks joining, so letters around it are shaped as separate runs.
        int i = 0;
        while (i < text.Length)
        {
            if (!IsArabicBaseLetter(text[i])) { sb.Append(text[i]); i++; continue; }
            int start = i;
            while (i < text.Length && IsArabicBaseLetter(text[i]) && text[i] != '\u0640') i++;
            ShapeRun(sb, text, start, i);
            // consume a non-letter separator that ended the run
            if (i < text.Length && !IsArabicBaseLetter(text[i])) { sb.Append(text[i]); i++; }
        }
        return sb.ToString();
    }

    private static void ShapeRun(StringBuilder sb, string text, int start, int end)
    {
        int n = end - start;
        for (int pos = 0; pos < n; pos++)
        {
            char c = text[start + pos];
            if (!Forms.TryGetValue(c, out var forms) || forms is null)
            {
                sb.Append(c); // unknown letter is drawn isolated as-is
                continue;
            }
            bool connectsBack = pos > 0 && JoinsRight(text[start + pos - 1]);
            bool connectsForward = JoinsRight(c) && pos + 1 < n && JoinsLeft(text[start + pos + 1]);

            int code =
                connectsBack && connectsForward && forms[3] != 0 ? forms[3] :
                connectsBack && forms[1] != 0 ? forms[1] :
                connectsForward && forms[2] != 0 ? forms[2] :
                forms[0];
            sb.Append(code != 0 ? (char)code : c);
        }
    }

    // ------------------------------------------------------------------ bidi

    private enum Dir { Neutral, Rtl, Ltr }

    private struct Run
    {
        public Dir Dir;
        public int Start;
        public int End;
        public Run(Dir dir, int start, int end) { Dir = dir; Start = start; End = end; }
    }

    /// <summary>Shape + reorder a logical Persian string for the game's LTR renderer.</summary>
    public static string ToDisplay(string? text)
    {
        if (string.IsNullOrEmpty(text)) return string.Empty;
        var sb = new StringBuilder(text.Length);
        int start = 0;
        for (int i = 0; i <= text.Length; i++)
        {
            if (i == text.Length || text[i] == '\n' || text[i] == '^')
            {
                if (i > start) sb.Append(ToDisplayLine(text[start..i]));
                if (i < text.Length) sb.Append(text[i]);
                start = i + 1;
            }
        }
        return sb.ToString();
    }

    // ------------------------------------------------------------------ rtl reveal (SpriteText)

    /// <summary>
    /// Produces a "typing" slice of a visual-order RTL string.
    ///
    /// The game reveals text by drawing the first <c>revealCount</c> characters
    /// (left-to-right). In a visual-order Persian line the sentence *start* is
    /// at the right end, so the visible part must be the line's suffix, padded
    /// with spaces so it stays anchored where the full line ends; lines that
    /// are not revealed yet are omitted.
    /// </summary>
    public static string TypeSlice(string visual, int revealCount, Func<string, int> measure, int targetWidth = 0)
    {
        if (revealCount <= 0) return string.Empty;
        if (revealCount >= visual.Length) return PinLines(visual, measure);

        var parts = SplitKeepSeparators(visual);
        int maxWidth = targetWidth > 0 ? targetWidth : 0;
        if (maxWidth <= 0)
        {
            foreach ((string line, char _) in parts)
            {
                if (line.Trim().Length == 0) continue;
                int w = measure(line);
                if (w > maxWidth) maxWidth = w;
            }
        }

        int remaining = revealCount;
        var sb = new StringBuilder(visual.Length);
        foreach ((string line, char sep) in parts)
        {
            if (remaining <= 0) break;
            if (line.Length == 0)
            {
                if (sep != default) sb.Append(sep);   // keep vertical spacing
                continue;
            }
            int k = Math.Min(line.Length, remaining);
            remaining -= k;
            string shown = line[^k..];
            sb.Append(PadLine(line, shown, measure, maxWidth));
            if (sep != default) sb.Append(sep);
            if (remaining <= 0) break;
        }
        return sb.ToString();
    }

    /// <summary>Rights-align every line of a visual-order string by leading spaces.</summary>
    public static string PinLines(string visual, Func<string, int> measure, int targetWidth = 0)
    {
        var parts = SplitKeepSeparators(visual);
        int maxWidth = targetWidth > 0 ? targetWidth : 0;
        if (maxWidth <= 0)
        {
            foreach ((string line, char _) in parts)
            {
                if (line.Trim().Length == 0) continue;
                int w = measure(line);
                if (w > maxWidth) maxWidth = w;
            }
        }
        if (maxWidth <= 0) return visual;

        var sb = new StringBuilder((int)(visual.Length * 1.5));
        foreach ((string line, char sep) in parts)
        {
            if (line.Trim().Length > 0)
                sb.Append(PadLine(line, line, measure, maxWidth));
            else
                sb.Append(line);   // keep blank lines verbatim (including all-space lines)
            if (sep != default) sb.Append(sep);
        }
        return sb.ToString();
    }

    private static string PadLine(string line, string shown, Func<string, int> measure, int targetWidth)
    {
        int spaceWidth = SpaceWidth(measure);
        int shownWidth = measure(shown);
        int padChars = Math.Max(0, (int)Math.Round((targetWidth - shownWidth) / (double)Math.Max(1, spaceWidth)));
        return new string(' ', padChars) + shown;
    }


    private static int _spaceWidth = -1;
    private static int SpaceWidth(Func<string, int> measure)
    {
        if (_spaceWidth > 0) return _spaceWidth;
        _spaceWidth = Math.Max(1, measure("    ") / 4);
        return _spaceWidth;
    }

    private static List<(string line, char sep)> SplitKeepSeparators(string s)
    {
        var parts = new List<(string, char)>();
        var cur = new StringBuilder();
        foreach (char c in s)
        {
            if (c is '\n' or '^')
            {
                parts.Add((cur.ToString(), c));
                cur.Clear();
            }
            else
            {
                cur.Append(c);
            }
        }
        parts.Add((cur.ToString(), default));
        return parts;
    }

    private static string ToDisplayLine(string line)
    {
        // Asset strings arrive already shaped (presentation forms) but still in
        // logical order; they must be reordered too. Base letters are shaped by
        // the caller before this method. Pure English lines stay untouched.
        if (!ContainsAnyRtl(line)) return line;

        // Mask game tokens ({0}, %x, $q, @, [TIME]...) so bidi cannot scramble them.
        var tokens = new List<string>();
        var sb = new StringBuilder(line.Length);
        for (int i = 0; i < line.Length; i++)
        {
            char c = line[i];
            if (c == '$' || c == '{' || c == '%' || c == '@' || c == '[')
            {
                int len = TokenLength(line, i);
                if (len > 1 || c == '@')
                {
                    tokens.Add(line.Substring(i, len));
                    sb.Append((char)('\uE000' + tokens.Count - 1));
                    i += len - 1;
                    continue;
                }
            }
            sb.Append(c);
        }
        string s = sb.ToString();

        // Split into direction runs, keeping punctuation/digits as separate runs.
        var runs = new List<Run>();
        int idx = 0;
        while (idx < s.Length)
        {
            if (s[idx] == ' ')
            {
                int j = idx + 1;
                while (j < s.Length && s[j] == ' ') j++;
                runs.Add(new Run(Dir.Neutral, idx, j));
                idx = j;
                continue;
            }
            Dir dir = Classify(s[idx]);
            int end = idx + 1;
            while (end < s.Length && s[end] != ' ')
            {
                Dir nextDir = Classify(s[end]);
                if (nextDir != dir) break;
                end++;
            }
            runs.Add(new Run(dir, idx, end));
            idx = end;
        }

        // Resolve neutral runs against their strong neighbours.
        for (int i = 0; i < runs.Count; i++)
        {
            if (runs[i].Dir != Dir.Neutral) continue;
            int p = i - 1;
            while (p >= 0 && runs[p].Dir == Dir.Neutral) p--;
            int n = i + 1;
            while (n < runs.Count && runs[n].Dir == Dir.Neutral) n++;
            Dir prev = p >= 0 ? runs[p].Dir : Dir.Neutral;
            Dir next = n < runs.Count ? runs[n].Dir : Dir.Neutral;
            bool hasSpace = false;
            for (int j = runs[i].Start; j < runs[i].End; j++)
                if (s[j] == ' ') { hasSpace = true; break; }

            Dir resolved;
            if (prev == Dir.Ltr && (next == Dir.Ltr || next == Dir.Neutral)) resolved = Dir.Ltr;
            else if (prev == Dir.Neutral && (next == Dir.Ltr || next == Dir.Neutral)) resolved = Dir.Ltr;
            else if (prev == Dir.Ltr && next == Dir.Rtl && !hasSpace) resolved = Dir.Ltr;
            else resolved = Dir.Rtl;
            var updated = runs[i];
            updated.Dir = resolved;
            runs[i] = updated;
        }

        // Merge adjacent runs of the same direction.
        var mergedRuns = new List<Run>();
        foreach (Run r in runs)
        {
            if (mergedRuns.Count > 0 && mergedRuns[^1].Dir == r.Dir)
            {
                Run m = mergedRuns[^1];
                m.End = r.End;
                mergedRuns[^1] = m;
            }
            else
            {
                mergedRuns.Add(r);
            }
        }

        // Emit runs from right to left; reverse RTL runs, mirror brackets.
        var outb = new StringBuilder(s.Length);
        for (int i = mergedRuns.Count - 1; i >= 0; i--)
        {
            Run r = mergedRuns[i];
            if (r.Dir == Dir.Rtl)
            {
                for (int j = r.End - 1; j >= r.Start; j--) outb.Append(Mirror(s[j]));
            }
            else
            {
                for (int j = r.Start; j < r.End; j++) outb.Append(s[j]);
            }
        }

        string result = outb.ToString();

        // Restore tokens and drop zero-width joiners (the shaped forms already
        // encode the joining decisions).
        var restored = new StringBuilder(result.Length);
        foreach (char c in result)
        {
            if (c >= '\uE000' && c < '\uE000' + tokens.Count) restored.Append(tokens[c - '\uE000']);
            else if (c is '\u200C' or '\u200D' or '\u200B' or '\u00AD') { }
            else restored.Append(c);
        }
        string display = restored.ToString();
        return display.Contains('\u200C') ? display.Replace("\u200C", "") : display;
    }

    private static Dir Classify(char c) =>
        IsRtl(c) ? Dir.Rtl : IsLtr(c) ? Dir.Ltr : Dir.Neutral;

    private static int TokenLength(string s, int i)
    {
        char c = s[i];
        if (c == '@') return 1;
        if (c == '[')
        {
            int close = s.IndexOf(']', i + 1);
            return close > i && close - i <= 40 ? close - i + 1 : 1;
        }
        if (c == '{')
        {
            int close = s.IndexOf('}', i + 1);
            return close > i && close - i <= 12 ? close - i + 1 : 1;
        }
        if (c == '%')
        {
            int j = i + 1;
            while (j < s.Length && (char.IsLetterOrDigit(s[j]) || s[j] == '_' || s[j] == ':')) j++;
            return j - i;
        }
        // $ command such as $e, $q, $1, $neutral...
        int k = i + 1;
        while (k < s.Length && (char.IsLetterOrDigit(s[k]) || s[k] == '_')) k++;
        return k - i;
    }
}

using System.Reflection;
using System.Text.Json.Serialization;
using BmFont;
using HarmonyLib;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.BellsAndWhistles;
using StardewValley.GameData;
using StardewValley.Menus;
using System.Text.Json;

namespace FarsiMod2;

public sealed class ModEntry : Mod
{
    public const string ModId = "Hana.FarsiMod2";
    public const string LanguageId = "Hana.FarsiMod2.Farsi";
    public const string LanguageCode = "fa-IR-v2"; // distinct from other Persian mods so both can coexist
    private const string FontAssetBase = "Mods/FarsiMod2/Assets/Fonts/fa2";
    private const string ButtonAsset = "Mods/FarsiMod2/Assets/LanguageButton";

    private readonly Dictionary<string, Dictionary<string, string>> _translations = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, SpriteFont> _spriteFonts = new(StringComparer.OrdinalIgnoreCase);
    private Dictionary<string, GlyphSheet>? _glyphSheets;
    private Harmony? _harmony;

    public override void Entry(IModHelper helper)
    {
        LoadTranslations();

        helper.Events.Content.AssetRequested += OnAssetRequested;
        helper.Events.GameLoop.SaveLoaded += OnSaveLoaded;
        LocalizedContentManager.OnLanguageChange += _ => InvalidateTranslations();
        helper.Events.GameLoop.ReturnedToTitle += OnReturnedToTitle;
        helper.Events.Input.ButtonPressed += OnButtonPressed;

        _harmony = new Harmony(ModManifest.UniqueID);
        PatchTextDraw(_harmony);
        this.Monitor.Log($"Farsi Mod 2 loaded ({_translations.Count} translation assets).", LogLevel.Info);
    }

    public override object? GetApi() => null;

    private void OnSaveLoaded(object? sender, SaveLoadedEventArgs e)
    {
        this.Monitor.Log($"Persian language active: {IsPersianActive()}", LogLevel.Debug);
    }

    private void InvalidateTranslations()
    {
        if (!IsPersianActive()) return;
        Helper.GameContent.InvalidateCache(asset => _translations.ContainsKey(asset.NameWithoutLocale.Name));
    }

    private void OnReturnedToTitle(object? sender, ReturnedToTitleEventArgs e) { }

    private void OnButtonPressed(object? sender, ButtonPressedEventArgs e)
    {
        // Debug helper: F7 in-game shows a sample of Persian text rendering.
        if (e.Button != SButton.F7 || !Context.IsWorldReady || !IsPersianActive()) return;
        Game1.activeClickableMenu = new DialogueBox("سلام! این متنِ آزمایشیِ مود فارسی است."
            + "^داره درست نمایش داده میشه؟" + "^۱۰۰۰ طلا (٪۵۰ تخفیف)");
    }

    private static bool IsPersianActive()
    {
        return LocalizedContentManager.CurrentLanguageCode == LocalizedContentManager.LanguageCode.mod
            && string.Equals(LocalizedContentManager.CurrentModLanguage?.LanguageCode, LanguageCode, StringComparison.OrdinalIgnoreCase);
    }

    private void LoadTranslations()
    {
        string dir = Path.Combine(Helper.DirectoryPath, "assets", "translations");
        if (!Directory.Exists(dir)) return;
        foreach (string file in Directory.EnumerateFiles(dir, "*.json"))
        {
            try
            {
                TranslationFile? data = JsonSerializer.Deserialize<TranslationFile>(File.ReadAllText(file));
                if (data == null || string.IsNullOrWhiteSpace(data.Asset) || data.Entries == null) continue;
                _translations[data.Asset] = data.Entries;
            }
            catch (Exception ex)
            {
                this.Monitor.Log($"Bad translation file {Path.GetFileName(file)}: {ex.Message}", LogLevel.Warn);
            }
        }
    }

    // ------------------------------------------------------------------ assets

    private void OnAssetRequested(object? sender, AssetRequestedEventArgs e)
    {
        string name = e.NameWithoutLocale.Name;

        // Advertise the language in every locale so the button always exists.
        if (name.Equals("Data/AdditionalLanguages", StringComparison.OrdinalIgnoreCase))
        {
            e.Edit(EditAdditionalLanguages, AssetEditPriority.Late);
            return;
        }

        if (name.Equals(ButtonAsset, StringComparison.OrdinalIgnoreCase))
        {
            e.LoadFromModFile<Texture2D>("assets/language-button.png", AssetLoadPriority.Exclusive);
            return;
        }

        if (!IsPersianActive()) return;

        if (name.Equals("Fonts/SpriteFont1", StringComparison.OrdinalIgnoreCase))
        {
            e.LoadFrom(() => GetSpriteFont("dialogue"), AssetLoadPriority.Exclusive);
            return;
        }
        if (name.Equals("Fonts/SmallFont", StringComparison.OrdinalIgnoreCase))
        {
            e.LoadFrom(() => GetSpriteFont("small"), AssetLoadPriority.Exclusive);
            return;
        }
        if (name.Equals(FontAssetBase, StringComparison.OrdinalIgnoreCase))
        {
            e.LoadFrom(() => new XmlSource(File.ReadAllText(Path.Combine(Helper.DirectoryPath, "assets", "fonts", "fa2.fnt"))), AssetLoadPriority.Exclusive);
            return;
        }
        // SpriteText loads page textures as "Fonts/<page file>": fa2_0.png -> Fonts/fa2_0
        if (name.Equals("Fonts/fa2_0", StringComparison.OrdinalIgnoreCase))
        {
            e.LoadFromModFile<Texture2D>("assets/fonts/fa2_0.png", AssetLoadPriority.Exclusive);
            return;
        }

        if (_translations.TryGetValue(name, out var entries))
        {
            e.Edit(asset =>
            {
                try
                {
                    if (name.Equals("Data/SecretNotes", StringComparison.OrdinalIgnoreCase))
                    {
                        var data = asset.AsDictionary<int, string>().Data;
                        foreach (var pair in entries)
                        {
                            if (int.TryParse(pair.Key, out int key) && data.ContainsKey(key))
                                data[key] = pair.Value;
                        }
                        return;
                    }
                    var dict = asset.AsDictionary<string, string>().Data;
                    foreach (var pair in entries)
                    {
                        if (dict.ContainsKey(pair.Key))
                            dict[pair.Key] = pair.Value;
                    }
                }
                catch (Exception ex)
                {
                    this.Monitor.Log($"Cannot translate '{name}': {ex.Message}", LogLevel.Warn);
                }
            }, AssetEditPriority.Late);
        }
    }

    private void EditAdditionalLanguages(IAssetData asset)
    {
        try
        {
            var list = asset.GetData<List<ModLanguage>>();
            list.RemoveAll(p => p.Id == LanguageId);
            list.Add(new ModLanguage
            {
                Id = LanguageId,
                LanguageCode = LanguageCode,
                ButtonTexture = ButtonAsset,
                UseLatinFont = false,
                FontFile = FontAssetBase,
                FontPixelZoom = 1f,
                FontApplyYOffset = false,
                SmallFontLineSpacing = 30,
                NumberComma = "٬",
                TimeFormat = "[HOURS_12]:[MINUTES]",
                ClockTimeFormat = "[HOURS_12]:[MINUTES]",
                ClockDateFormat = "[DAY_OF_WEEK] [DAY_OF_MONTH]"
            });
        }
        catch (Exception ex)
        {
            this.Monitor.Log($"Failed to register the Persian language: {ex.Message}", LogLevel.Error);
        }
    }

    // ------------------------------------------------------------------ fonts

    private SpriteFont GetSpriteFont(string name)
    {
        if (_spriteFonts.TryGetValue(name, out SpriteFont? cached)) return cached;

        var sheets = _glyphSheets ??= LoadGlyphSheets();
        GlyphSheet sheet = sheets.TryGetValue(name, out GlyphSheet? s) ? s! : throw new InvalidOperationException($"glyph sheet '{name}' missing");

        Texture2D texture = Helper.ModContent.Load<Texture2D>($"assets/fonts/{name}.png");
        var records = sheet.Glyphs.OrderBy(g => g.Char[0]).ToList();
        var bounds = new List<Rectangle>(records.Count);
        var cropping = new List<Rectangle>(records.Count);
        var characters = new List<char>(records.Count);
        var kerning = new List<Vector3>(records.Count);
        foreach (GlyphRecord g in records)
        {
            bounds.Add(new Rectangle(g.X, g.Y, g.W, g.H));
            cropping.Add(new Rectangle(g.XOffset, g.SpriteCropY, g.W, g.H));
            characters.Add(g.Char[0]);
            kerning.Add(new Vector3(0f, g.XAdvance, 0f));
        }
        SpriteFont font = new(texture, bounds, cropping, characters, sheet.LineSpacing, sheet.Spacing, kerning, '?');
        _spriteFonts[name] = font;
        return font;
    }

    private Dictionary<string, GlyphSheet> LoadGlyphSheets()
    {
        var sheets = new Dictionary<string, GlyphSheet>(StringComparer.OrdinalIgnoreCase);
        foreach (string name in new[] { "dialogue", "small" })
        {
            string path = Path.Combine(Helper.DirectoryPath, "assets", "fonts", name + ".json");
            GlyphSheet? data = JsonSerializer.Deserialize<GlyphSheet>(File.ReadAllText(path));
            if (data != null) sheets[name] = data;
        }
        return sheets;
    }

    // ------------------------------------------------------------------ text pipeline hooks

    private void PatchTextDraw(Harmony harmony)
    {
        MethodInfo drawPrefix = typeof(ModEntry).GetMethod(nameof(TransformDrawnText), BindingFlags.Static | BindingFlags.NonPublic)!;
        MethodInfo measurePrefix = typeof(ModEntry).GetMethod(nameof(TransformMeasuredText), BindingFlags.Static | BindingFlags.NonPublic)!;
        MethodInfo spriteTextPrefix = typeof(ModEntry).GetMethod(nameof(TransformSpriteText), BindingFlags.Static | BindingFlags.NonPublic)!;
        int patched = 0;

        foreach (MethodInfo method in typeof(SpriteBatch).GetMethods(BindingFlags.Public | BindingFlags.Instance))
        {
            if (method.Name != nameof(SpriteBatch.DrawString)) continue;
            ParameterInfo[] p = method.GetParameters();
            if (p.Length >= 2 && p[0].ParameterType == typeof(SpriteFont) && p[1].ParameterType == typeof(string))
            {
                harmony.Patch(method, prefix: new HarmonyMethod(drawPrefix));
                patched++;
            }
            else if (p.Length >= 2 && p[0].ParameterType == typeof(SpriteFont) && p[1].ParameterType == typeof(System.Text.StringBuilder))
            {
                harmony.Patch(method, prefix: new HarmonyMethod(_stringBuilderPrefix ??= typeof(ModEntry).GetMethod(nameof(TransformDrawnStringBuilder), BindingFlags.Static | BindingFlags.NonPublic)));
                patched++;
            }
        }
        foreach (MethodInfo method in typeof(SpriteFont).GetMethods(BindingFlags.Public | BindingFlags.Instance))
        {
            if (method.Name != nameof(SpriteFont.MeasureString)) continue;
            ParameterInfo[] p = method.GetParameters();
            if (p.Length >= 1 && p[0].ParameterType == typeof(string))
            {
                harmony.Patch(method, prefix: new HarmonyMethod(measurePrefix));
                patched++;
            }
        }
        MethodInfo? spriteText = AccessTools.Method(typeof(SpriteText), nameof(SpriteText.drawString));
        if (spriteText != null)
        {
            harmony.Patch(spriteText, prefix: new HarmonyMethod(spriteTextPrefix));
            patched++;
        }
        this.Monitor.Log($"Patched {patched} text method(s).", LogLevel.Trace);
    }

    private static MethodInfo? _stringBuilderPrefix;

    /// <summary>SpriteFont path (HUD/menus). Only strings that are still logical
    /// Persian are transformed — asset strings are already display-ready.</summary>
    private static void TransformDrawnText(ref string text)
    {
        if (!IsPersianActive() || !FarsiText.ContainsAnyRtl(text)) return;
        string shaped = FarsiText.ContainsBasePersian(text) ? FarsiText.Shape(text) : text;
        text = FarsiText.ToDisplay(shaped);
    }

    private static void TransformDrawnStringBuilder(ref System.Text.StringBuilder text)
    {
        if (!IsPersianActive() || text == null || !FarsiText.ContainsAnyRtl(text.ToString())) return;
        string raw = text.ToString();
        string shaped = FarsiText.ContainsBasePersian(raw) ? FarsiText.Shape(raw) : raw;
        // Do not mutate the caller's builder: tooltips draw the same builder several
        // times for shadow/outline, and mutating it would reorder the text each pass.
        text = new System.Text.StringBuilder(FarsiText.ToDisplay(shaped));
    }

    private static void TransformMeasuredText(ref string text)
    {
        if (!IsPersianActive() || !FarsiText.ContainsAnyRtl(text)) return;
        string shaped = FarsiText.ContainsBasePersian(text) ? FarsiText.Shape(text) : text;
        text = FarsiText.ToDisplay(shaped);
    }

    /// <summary>SpriteText path (dialogue/story portraits; BMFont). Runs the
    /// RTL right-to-left "typing" reveal and right-aligns the lines.</summary>
    private static void TransformSpriteText(SpriteBatch b, ref string s, int x, int y, ref int characterPosition, int width, int height, float alpha, float layerDepth, bool junimoText, int drawBGScroll, string placeHolderScrollWidthText, Color? color)
    {
        if (!IsPersianActive() || string.IsNullOrEmpty(s) || !FarsiText.ContainsAnyRtl(s)) return;

        // Convert both player-entered base letters and logical asset strings into
        // display order. Assets are pre-shaped but still logical.
        string logical = FarsiText.ContainsBasePersian(s) ? FarsiText.Shape(s) : s;
        bool wrap = !junimoText && drawBGScroll == -1 && width > 0 && width < 2000;
        s = wrap ? WrapLogicalPersian(logical, width - 16) : FarsiText.ToDisplay(logical);

        // Apply the right-to-left typing reveal when the game is still revealing
        // this string.
        Func<string, int> widthOf = text => SpriteText.getWidthOfString(text);
        int targetWidth = width > 0 && width < 2000 ? width - 16 : 0;
        if (characterPosition < s.Length)
            s = FarsiText.TypeSlice(s, characterPosition, widthOf, targetWidth);
        else
            s = FarsiText.PinLines(s, widthOf, targetWidth);
        characterPosition = int.MaxValue;
    }

    /// <summary>Wrap logical Persian into lines before bidi reordering, so the
    /// first words stay on the first (top) line and long dialogue doesn't push
    /// the beginning of the sentence to the bottom.</summary>
    private static string WrapLogicalPersian(string text, int width)
    {
        var result = new System.Text.StringBuilder(text.Length + 16);
        string[] paragraphs = text.Split('^');
        for (int p = 0; p < paragraphs.Length; p++)
        {
            string line = string.Empty;
            foreach (string word in paragraphs[p].Split(' '))
            {
                string candidate = line.Length == 0 ? word : line + " " + word;
                if (line.Length > 0 && SpriteText.getWidthOfString(candidate) > width)
                {
                    result.Append(FarsiText.ToDisplay(line));
                    result.Append('^');
                    line = word;
                }
                else
                {
                    line = candidate;
                }
            }
            result.Append(FarsiText.ToDisplay(line));
            if (p < paragraphs.Length - 1) result.Append('^');
        }
        return result.ToString();
    }

    // ------------------------------------------------------------------ data models

    private sealed class TranslationFile
    {
        [JsonPropertyName("asset")] public string Asset { get; set; } = "";
        [JsonPropertyName("entries")] public Dictionary<string, string>? Entries { get; set; }
    }

    private sealed class GlyphSheet
    {
        [JsonPropertyName("lineSpacing")] public int LineSpacing { get; set; }
        [JsonPropertyName("spacing")] public float Spacing { get; set; }
        [JsonPropertyName("glyphs")] public List<GlyphRecord> Glyphs { get; set; } = new();
    }

    private sealed class GlyphRecord
    {
        [JsonPropertyName("char")] public string Char { get; set; } = "?";
        [JsonPropertyName("x")] public int X { get; set; }
        [JsonPropertyName("y")] public int Y { get; set; }
        [JsonPropertyName("w")] public int W { get; set; }
        [JsonPropertyName("h")] public int H { get; set; }
        [JsonPropertyName("xoffset")] public int XOffset { get; set; }
        [JsonPropertyName("sprite_crop_y")] public int SpriteCropY { get; set; }
        [JsonPropertyName("xadvance")] public int XAdvance { get; set; }
    }
}

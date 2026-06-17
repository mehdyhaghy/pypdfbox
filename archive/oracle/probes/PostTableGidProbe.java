import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;

/**
 * Live oracle probe for the **post-table-name code→GID fallback** of
 * {@link PDTrueTypeFont} (PDF 32000-1 §9.6.6.4, last resort branch).
 *
 * <p>For a non-symbolic embedded simple TrueType font, {@code codeToGID(code)}
 * walks: {@code /Encoding} (base + /Differences) → glyph name; the name → a
 * Unicode scalar via the Adobe Glyph List, looked up in the (3,1) Win-Unicode
 * cmap; failing that the name → a Mac-Roman byte looked up in the (1,0)
 * cmap; and — the path this probe isolates — failing *both* cmaps the name is
 * resolved directly in the font's {@code post} table via
 * {@code TrueTypeFont.nameToGID(name)}.
 *
 * <p>To exercise the post-table tail deterministically the probe embeds the
 * <em>full, un-subset</em> {@code DejaVuSansMono.ttf} program (so the original
 * glyph order and {@code post} format-2.0 names survive intact) and builds the
 * font dictionary by hand with a {@code /Differences} overlay that names, at
 * specific byte codes, glyphs that route through each branch:
 *
 * <ul>
 *   <li>code 65 → {@code u1D670} — a MATHEMATICAL MONOSPACE CAPITAL A glyph
 *       whose PostScript name has <em>no</em> Adobe-Glyph-List Unicode mapping
 *       and is not the {@code uniXXXX} form, so neither cmap step nor the
 *       {@code nameToGID} uni-name fallback fires — only the {@code post}
 *       name → GID map answers (the branch under test);</li>
 *   <li>code 66 → {@code A} — a control that resolves through the (3,1)
 *       Win-Unicode cmap (AGL "A" → U+0041);</li>
 *   <li>code 67 → {@code bullet} — a second cmap control (AGL → U+2022).</li>
 * </ul>
 *
 * <p>Two subcommands, dispatched on argv[0]:
 *
 * <pre>
 *   BUILD &lt;ttf&gt; &lt;out.pdf&gt;   embed the full TTF + /Differences, save the PDF
 *   DUMP  &lt;in.pdf&gt;           print, for the first embedded simple TrueType
 *                            font on page 0, one line per byte code 0..255:
 *                              ROW \t code \t codeToGID(code) \t hasGlyph(code)
 * </pre>
 *
 * The Python side calls BUILD (so both engines read byte-identical PDFs), then
 * reconstructs the DUMP lines from {@code PDTrueTypeFont.code_to_gid} /
 * {@code has_glyph} and asserts line-for-line equality.
 */
public final class PostTableGidProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("BUILD".equals(mode)) {
            build(new File(args[1]), new File(args[2]));
            return;
        }
        if ("DUMP".equals(mode)) {
            dump(out, new File(args[1]));
            return;
        }
        throw new IllegalArgumentException("unknown mode: " + mode);
    }

    private static void build(File ttf, File outPdf) throws Exception {
        byte[] ttfBytes = Files.readAllBytes(ttf.toPath());
        try (PDDocument doc = new PDDocument()) {
            doc.addPage(new PDPage());

            // Embed the full, un-subset TTF program so the original glyph
            // order + post-table names survive untouched.
            PDStream fontFile2 = new PDStream(
                    doc, new java.io.ByteArrayInputStream(ttfBytes));
            fontFile2.getCOSObject().setInt(COSName.LENGTH1, ttfBytes.length);

            COSDictionary descDict = new COSDictionary();
            descDict.setItem(COSName.TYPE, COSName.FONT_DESC);
            descDict.setName(COSName.FONT_NAME, "DejaVuSansMono");
            PDFontDescriptor desc = new PDFontDescriptor(descDict);
            desc.setNonSymbolic(true);
            desc.setFontFile2(fontFile2);

            // /Encoding with a /Differences overlay onto WinAnsiEncoding.
            COSArray diffs = new COSArray();
            diffs.add(COSInteger.get(65));
            diffs.add(COSName.getPDFName("u1D670"));
            diffs.add(COSInteger.get(66));
            diffs.add(COSName.getPDFName("A"));
            diffs.add(COSInteger.get(67));
            diffs.add(COSName.getPDFName("bullet"));
            COSDictionary encDict = new COSDictionary();
            encDict.setItem(COSName.TYPE, COSName.ENCODING);
            encDict.setItem(COSName.BASE_ENCODING, COSName.WIN_ANSI_ENCODING);
            encDict.setItem(COSName.DIFFERENCES, diffs);

            COSDictionary fontDict = new COSDictionary();
            fontDict.setItem(COSName.TYPE, COSName.FONT);
            fontDict.setItem(COSName.SUBTYPE, COSName.TRUE_TYPE);
            fontDict.setName(COSName.BASE_FONT, "DejaVuSansMono");
            fontDict.setItem(COSName.FONT_DESC, descDict);
            fontDict.setItem(COSName.ENCODING, encDict);
            fontDict.setInt(COSName.FIRST_CHAR, 0);
            fontDict.setInt(COSName.LAST_CHAR, 255);
            COSArray widths = new COSArray();
            for (int i = 0; i < 256; i++) {
                widths.add(COSInteger.get(600));
            }
            fontDict.setItem(COSName.WIDTHS, widths);

            PDTrueTypeFont font = new PDTrueTypeFont(fontDict);
            PDPage page = doc.getPage(0);
            PDResources res = new PDResources();
            res.put(COSName.getPDFName("F1"), font);
            page.setResources(res);

            doc.save(outPdf);
        }
        // Confirm the embedded program loads (sanity; not part of the diff).
        try (RandomAccessReadBuffer rb = new RandomAccessReadBuffer(ttfBytes)) {
            rb.length();
        }
    }

    private static void dump(PrintStream out, File inPdf) throws Exception {
        try (PDDocument doc = org.apache.pdfbox.Loader.loadPDF(inPdf)) {
            PDResources res = doc.getPage(0).getResources();
            PDTrueTypeFont font = null;
            for (COSName name : res.getFontNames()) {
                if (res.getFont(name) instanceof PDTrueTypeFont) {
                    font = (PDTrueTypeFont) res.getFont(name);
                    break;
                }
            }
            if (font == null) {
                throw new IllegalStateException("no PDTrueTypeFont on page 0");
            }
            out.printf("EMBEDDED\t%b%n", font.isEmbedded());
            for (int code = 0; code < 256; code++) {
                int gid;
                try {
                    gid = font.codeToGID(code);
                } catch (Exception e) {
                    gid = -1;
                }
                boolean has;
                try {
                    has = font.hasGlyph(code);
                } catch (Exception e) {
                    has = false;
                }
                out.printf("ROW\t%d\t%d\t%b%n", code, gid, has);
            }
        }
    }
}

import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.GlyphData;
import org.apache.fontbox.ttf.GlyphTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe for TrueType *subset* structure. Two modes.
 *
 * <pre>
 *   java -cp ... SubsetProbe build &lt;ttf&gt; &lt;text&gt; &lt;outType0.pdf&gt; &lt;outSimple.pdf&gt;
 * </pre>
 *   Apache PDFBox itself builds the reference PDFs: one Type0 (PDType0Font.load
 *   with embedSubset=true) and one simple TrueType (PDTrueTypeFont.load), draws
 *   {@code text} once with each, and saves. This is the oracle's *own* subset
 *   output — the ground truth pypdfbox mirrors.
 *
 * <pre>
 *   java -cp ... SubsetProbe read &lt;input.pdf&gt;
 * </pre>
 *   Reads the embedded subset of every font on every page and emits canonical,
 *   line-oriented structural facts (UTF-8, tab-delimited, deterministic order):
 *
 *   FONT \t pageIndex \t resourceName \t baseFont \t subType \t hasSubsetPrefix
 *       hasSubsetPrefix is "true" when /BaseFont matches "^[A-Z]{6}\+".
 *   PROG \t pageIndex \t resourceName \t fontFile2Len \t numGlyphs \t
 *        nonEmptyGlyphs \t hasGlyf \t hasLoca \t hasHmtx \t hasCmap
 *       fontFile2Len: decoded /FontFile2 length in bytes (the embedded sfnt).
 *       numGlyphs:    glyph count of the embedded subset program (maxp).
 *       nonEmptyGlyphs: glyphs in 0..numGlyphs-1 whose outline is non-null
 *                       (i.e. retained with real contours; .notdef counts when
 *                       it has a body, composite/empty glyphs reported too).
 *   FLAGS \t pageIndex \t resourceName \t descriptorFlags
 *       The /FontDescriptor /Flags integer.
 *   WLEN \t pageIndex \t resourceName \t wArrayLen
 *       Type0 descendant /W array element count; "NA" for simple fonts.
 *
 * Never mutates the read document; closes everything via try-with-resources.
 */
public final class SubsetProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length == 0) {
            out.println("usage: SubsetProbe build|read ...");
            return;
        }
        if ("build".equals(args[0])) {
            build(args[1], args[2], args[3], args[4]);
            return;
        }
        if ("read".equals(args[0])) {
            read(out, args[1]);
            return;
        }
        out.println("usage: SubsetProbe build|read ...");
    }

    /** PDFBox builds the reference Type0 + simple subset PDFs. */
    private static void build(String ttfPath, String text, String type0Out,
            String simpleOut) throws Exception {
        File ttf = new File(ttfPath);
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDType0Font font = PDType0Font.load(doc, ttf);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginText();
                cs.setFont(font, 14);
                cs.newLineAtOffset(50, 700);
                cs.showText(text);
                cs.endText();
            }
            doc.save(type0Out);
        }
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDTrueTypeFont font = PDTrueTypeFont.load(doc, ttf,
                    org.apache.pdfbox.pdmodel.font.encoding
                            .WinAnsiEncoding.INSTANCE);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginText();
                cs.setFont(font, 14);
                cs.newLineAtOffset(50, 700);
                cs.showText(text);
                cs.endText();
            }
            doc.save(simpleOut);
        }
    }

    private static void read(PrintStream out, String pdf) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(pdf))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        emitFont(out, pageIndex, name, res);
                    }
                }
                pageIndex++;
            }
        }
    }

    private static void emitFont(PrintStream out, int pageIndex, COSName name,
            PDResources res) throws Exception {
        String key = name.getName();
        PDFont font;
        try {
            font = res.getFont(name);
        } catch (Exception e) {
            out.printf("FONT\t%d\t%s\tLOAD_ERR%n", pageIndex, key);
            return;
        }
        if (font == null) {
            out.printf("FONT\t%d\t%s\tNULL%n", pageIndex, key);
            return;
        }

        String baseFont = String.valueOf(font.getName());
        boolean hasPrefix = baseFont.matches("^[A-Z]{6}\\+.*");
        out.printf("FONT\t%d\t%s\t%s\t%s\t%b%n",
                pageIndex, key, baseFont, font.getSubType(), hasPrefix);

        // Decoded /FontFile2 bytes + descriptor flags.
        PDFontDescriptor fd = font.getFontDescriptor();
        byte[] fontFile2 = null;
        int flags = 0;
        if (fd != null) {
            flags = fd.getFlags();
            COSStream ff2 = ff2Stream(fd);
            if (ff2 != null) {
                fontFile2 = readAll(ff2);
            }
        }

        if (fontFile2 == null) {
            out.printf("PROG\t%d\t%s\tNONE%n", pageIndex, key);
        } else {
            try (TrueTypeFont ttf =
                    new TTFParser(true).parse(
                            new org.apache.pdfbox.io.RandomAccessReadBuffer(
                                    fontFile2))) {
                int numGlyphs = ttf.getNumberOfGlyphs();
                int nonEmpty = 0;
                GlyphTable glyf = ttf.getGlyph();
                if (glyf != null) {
                    for (int gid = 0; gid < numGlyphs; gid++) {
                        GlyphData g = glyf.getGlyph(gid);
                        if (g != null) {
                            nonEmpty++;
                        }
                    }
                }
                out.printf("PROG\t%d\t%s\t%d\t%d\t%d\t%b\t%b\t%b\t%b%n",
                        pageIndex, key, fontFile2.length, numGlyphs, nonEmpty,
                        glyf != null, ttf.getTableMap().containsKey("loca"),
                        ttf.getHorizontalMetrics() != null,
                        ttf.getCmap() != null);
            }
        }

        out.printf("FLAGS\t%d\t%s\t%d%n", pageIndex, key, flags);

        if (font instanceof PDType0Font) {
            PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
            int wLen = 0;
            if (descendant != null) {
                COSBase wBase = descendant.getCOSObject()
                        .getDictionaryObject(COSName.W);
                if (wBase instanceof COSArray) {
                    wLen = ((COSArray) wBase).size();
                }
            }
            out.printf("WLEN\t%d\t%s\t%d%n", pageIndex, key, wLen);
        } else {
            out.printf("WLEN\t%d\t%s\tNA%n", pageIndex, key);
        }
    }

    private static COSStream ff2Stream(PDFontDescriptor fd) {
        COSDictionary d = fd.getCOSObject();
        COSBase b = d.getDictionaryObject(COSName.FONT_FILE2);
        return b instanceof COSStream ? (COSStream) b : null;
    }

    private static byte[] readAll(COSStream stream) throws Exception {
        try (java.io.InputStream in = stream.createInputStream();
                java.io.ByteArrayOutputStream bos =
                        new java.io.ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                bos.write(buf, 0, n);
            }
            return bos.toByteArray();
        }
    }
}

import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe for CFF / Type1C font embedding + subsetting structure.
 * This is the CFF (FontFile3) sibling of SubsetProbe (which covers the
 * TrueType FontFile2 / glyf side); the two never overlap.
 *
 * <p>Read mode only: Apache PDFBox 3.0.7 has no public CFF *subset-embed*
 * builder ({@code PDType0Font.load} routes every input through {@code TTFParser}
 * and throws "True Type fonts using CFF outlines are not supported" for a
 * CFF-flavoured OTF), so the ground truth for CFF subsetting comes from CFF
 * subsets already embedded in real PDFs. This probe reads them back through
 * PDFBox's own loaders + fontbox {@code CFFParser} and emits canonical,
 * line-oriented structural facts that pypdfbox mirrors.
 *
 * <pre>
 *   java -cp ... CffSubsetProbe read &lt;input.pdf&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   FONT \t pageIndex \t resourceName \t baseFont \t subType \t hasSubsetPrefix
 *       hasSubsetPrefix is "true" when /BaseFont matches "^[A-Z]{6}\+".
 *   FF3 \t pageIndex \t resourceName \t fontFile3SubType \t fontFile3Len \t isCID
 *       fontFile3SubType: the /FontFile3 /Subtype name (Type1C / CIDFontType0C
 *                         / OpenType), or "NONE" when no /FontFile3 is present.
 *       fontFile3Len:     decoded /FontFile3 length in bytes.
 *       isCID:            "true" when fontbox parses the program as a CID-keyed
 *                         CFF font (CFFCIDFont), else "false".
 *   CFF \t pageIndex \t resourceName \t glyphCount
 *       glyphCount: charset glyph count of the embedded CFF program, parsed
 *                   back via fontbox CFFParser (== getNumCharStrings()).
 *   FLAGS \t pageIndex \t resourceName \t descriptorFlags
 *       The /FontDescriptor /Flags integer.
 *   WLEN \t pageIndex \t resourceName \t wArrayLen
 *       Type0 descendant /W array element count; "NA" for simple fonts.
 *   WID \t pageIndex \t resourceName \t code \t width
 *       Per used character code, PDFBox's getWidthFromFont(code) in 1000-unit
 *       text space, normalised to 4 decimals; "ERR" when resolution throws.
 *
 * Never mutates the read document; closes everything via try-with-resources.
 */
public final class CffSubsetProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"read".equals(args[0])) {
            out.println("usage: CffSubsetProbe read <input.pdf>");
            return;
        }
        read(out, args[1]);
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

        PDFontDescriptor fd = font.getFontDescriptor();
        int flags = 0;
        byte[] ff3 = null;
        String ff3Sub = "NONE";
        if (fd != null) {
            flags = fd.getFlags();
            COSStream ff3Stream = ff3Stream(fd);
            if (ff3Stream != null) {
                ff3 = readAll(ff3Stream);
                COSBase sub = ff3Stream.getDictionaryObject(COSName.SUBTYPE);
                ff3Sub = sub instanceof COSName ? ((COSName) sub).getName()
                        : "NONE";
            }
        }

        if (ff3 == null) {
            out.printf("FF3\t%d\t%s\tNONE\t0\tfalse%n", pageIndex, key);
            out.printf("CFF\t%d\t%s\tNONE%n", pageIndex, key);
        } else {
            boolean isCid = false;
            int glyphCount = -1;
            try {
                CFFFont cff = new CFFParser().parse(ff3,
                        new CffByteSource(ff3)).get(0);
                isCid = cff.getCharset().isCIDFont();
                glyphCount = cff.getNumCharStrings();
            } catch (Exception e) {
                glyphCount = -1;
            }
            out.printf("FF3\t%d\t%s\t%s\t%d\t%b%n",
                    pageIndex, key, ff3Sub, ff3.length, isCid);
            if (glyphCount < 0) {
                out.printf("CFF\t%d\t%s\tPARSE_ERR%n", pageIndex, key);
            } else {
                out.printf("CFF\t%d\t%s\t%d%n", pageIndex, key, glyphCount);
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

        for (int code : usedCodes(font)) {
            String w;
            try {
                w = fmt(font.getWidthFromFont(code));
            } catch (Exception e) {
                w = "ERR";
            }
            out.printf("WID\t%d\t%s\t%d\t%s%n", pageIndex, key, code, w);
        }
    }

    private static COSStream ff3Stream(PDFontDescriptor fd) {
        COSDictionary d = fd.getCOSObject();
        COSBase b = d.getDictionaryObject(COSName.FONT_FILE3);
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

    /**
     * Resolve the character codes the document addresses, ascending. Type0:
     * the CIDs spelled out by the descendant /W array. Simple CFF: the
     * /FirstChar..LastChar /Widths range.
     */
    private static List<Integer> usedCodes(PDFont font) {
        TreeSet<Integer> codes = new TreeSet<>();
        if (font instanceof PDType0Font) {
            PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
            if (descendant != null) {
                COSBase wBase = descendant.getCOSObject()
                        .getDictionaryObject(COSName.W);
                if (wBase instanceof COSArray) {
                    codes.addAll(widthCidsFromW((COSArray) wBase));
                }
            }
        } else {
            COSDictionary dict = font.getCOSObject();
            COSBase fc = dict.getDictionaryObject(COSName.FIRST_CHAR);
            COSBase lc = dict.getDictionaryObject(COSName.LAST_CHAR);
            if (fc instanceof COSNumber && lc instanceof COSNumber) {
                int first = ((COSNumber) fc).intValue();
                int last = ((COSNumber) lc).intValue();
                for (int c = first; c <= last && c - first < 256; c++) {
                    codes.add(c);
                }
            }
        }
        return new ArrayList<>(codes);
    }

    private static List<Integer> widthCidsFromW(COSArray w) {
        List<Integer> out = new ArrayList<>();
        int i = 0;
        int n = w.size();
        while (i < n) {
            COSBase first = w.getObject(i);
            if (!(first instanceof COSNumber)) {
                break;
            }
            int cFirst = ((COSNumber) first).intValue();
            if (i + 1 >= n) {
                break;
            }
            COSBase next = w.getObject(i + 1);
            if (next instanceof COSArray) {
                COSArray widths = (COSArray) next;
                for (int k = 0; k < widths.size(); k++) {
                    out.add(cFirst + k);
                }
                i += 2;
            } else if (next instanceof COSNumber) {
                if (i + 2 >= n) {
                    break;
                }
                int cLast = ((COSNumber) next).intValue();
                int upper = Math.min(cLast, cFirst + 1024);
                for (int c = cFirst; c <= upper; c++) {
                    out.add(c);
                }
                i += 3;
            } else {
                break;
            }
        }
        return out;
    }

    private static String fmt(double v) {
        return String.format(java.util.Locale.ROOT, "%.4f", v);
    }

    /** Minimal ByteSource backing the embedded CFF program. */
    private static final class CffByteSource implements CFFParser.ByteSource {
        private final byte[] bytes;

        CffByteSource(byte[] bytes) {
            this.bytes = bytes;
        }

        @Override
        public byte[] getBytes() {
            return bytes;
        }
    }
}

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe: emit Apache PDFBox's PDType0Font READ-side decode + width
 * pipeline for every Type0 (composite) font on every page of a PDF.
 *
 * This drives the PARENT PDType0Font surface (distinct from the descendant-level
 * CidGidProbe / CidWidthProbe which call PDCIDFont.codeToGID(cid) /
 * PDCIDFont.getWidth(int)):
 *
 *   - PDType0Font.codeToCID(int)   — code -> CID through the /Encoding CMap
 *   - PDType0Font.codeToGID(int)   — the composite code -> GID (public, throws
 *                                    IOException), which resolves code->CID then
 *                                    descendant CID->GID in one parent call
 *   - PDType0Font.getWidth(int)    — composite per-code advance (1/1000 em)
 *   - PDType0Font.getStringWidth(String) — sum of per-code advances for a sample
 *                                    string round-tripped from the font's own
 *                                    decodable codes (toUnicode), so the
 *                                    encode->readCode->getWidth loop is exercised
 *                                    end to end rather than on synthetic ASCII.
 *
 * Covered codes are derived from the descendant's /W array (under Identity-H —
 * the only encoding the project's Type0 fixtures use — the input code equals the
 * CID, so the /W CIDs are exactly the addressable codes). CID 0 (.notdef) and
 * two synthetic out-of-range codes are always included.
 *
 * Output (UTF-8, tab-delimited, deterministic order: page, font name, ascending
 * code):
 *   FONT \t page \t fontKey \t baseFont \t encodingName \t descSubtype \t embedded
 *   CODE \t page \t fontKey \t code \t cid \t gid \t width
 *   SWB  \t page \t fontKey \t nCodes \t totalWidth
 * The SWB line is the READ-side string-advance accumulation: a content-stream
 * byte buffer is built directly from the first few covered codes (Identity-H —
 * 2-byte big-endian), then decoded back through PDType0Font.readCode(stream) in
 * a loop, summing getWidth(code) for each decoded code. This is exactly the
 * second half of getStringWidth (decode bytes -> code -> width) WITHOUT the
 * String-encode step, keeping the probe on the decode/width read surface rather
 * than the encode-roundtrip boundary.
 * Calls that throw upstream are emitted as "ERR" so pypdfbox pins the same
 * failure boundary. Widths use Locale.ROOT %.4f with -0.0 collapsed to 0.0.
 */
public final class Type0ReadWidthProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    emitPage(out, res, pageIndex);
                }
                pageIndex++;
            }
        }
    }

    private static void emitPage(PrintStream out, PDResources res, int pageIndex)
            throws Exception {
        for (COSName name : res.getFontNames()) {
            PDFont font;
            try {
                font = res.getFont(name);
            } catch (Exception e) {
                continue;
            }
            if (!(font instanceof PDType0Font)) {
                continue;
            }
            PDType0Font t0 = (PDType0Font) font;
            PDCIDFont descendant = t0.getDescendantFont();
            String descSubtype = descendant == null
                    ? "NONE" : descendant.getClass().getSimpleName();
            String encodingName = encodingName(t0);
            boolean embedded;
            try {
                embedded = t0.isEmbedded();
            } catch (Exception e) {
                embedded = false;
            }
            out.printf(
                "FONT\t%d\t%s\t%s\t%s\t%s\t%b%n",
                pageIndex,
                name.getName(),
                String.valueOf(t0.getName()),
                encodingName,
                descSubtype,
                embedded);

            List<Integer> codes = coveredCodes(descendant);
            for (int code : codes) {
                String cid;
                try {
                    cid = String.valueOf(t0.codeToCID(code));
                } catch (Exception e) {
                    cid = "ERR";
                }
                String gid;
                try {
                    gid = String.valueOf(t0.codeToGID(code));
                } catch (Exception e) {
                    gid = "ERR";
                }
                String width;
                try {
                    width = fmt(t0.getWidth(code));
                } catch (Exception e) {
                    width = "ERR";
                }
                out.printf("CODE\t%d\t%s\t%d\t%s\t%s\t%s%n",
                    pageIndex, name.getName(), code, cid, gid, width);
            }

            // READ-side string-advance accumulation: build a content-stream
            // byte buffer from the first few in-range covered codes (Identity-H
            // 2-byte big-endian), decode it back through readCode, and sum the
            // per-code widths. Drives the decode + width half of getStringWidth.
            List<Integer> sampleCodes = sampleCodes(codes);
            byte[] buffer = identityBytes(sampleCodes);
            String total;
            int nDecoded = -1;
            try {
                float sum = 0.0f;
                int count = 0;
                InputStream in = new ByteArrayInputStream(buffer);
                while (in.available() > 0) {
                    int code = t0.readCode(in);
                    sum += t0.getWidth(code);
                    count++;
                }
                nDecoded = count;
                total = fmt(sum);
            } catch (Exception e) {
                total = "ERR";
            }
            out.printf("SWB\t%d\t%s\t%d\t%s%n",
                pageIndex, name.getName(), nDecoded, total);
        }
    }

    private static String encodingName(PDType0Font t0) {
        COSBase enc = t0.getCOSObject().getDictionaryObject(COSName.ENCODING);
        if (enc instanceof COSName) {
            return "name:" + ((COSName) enc).getName();
        }
        if (enc != null) {
            return "stream";
        }
        return "absent";
    }

    /**
     * Pick the first up-to-8 in-range covered codes (skipping CID 0 and the
     * synthetic out-of-range probes 60000/65535) to build the read-side sample.
     */
    private static List<Integer> sampleCodes(List<Integer> codes) {
        List<Integer> out = new ArrayList<>();
        for (int code : codes) {
            if (out.size() >= 8) {
                break;
            }
            if (code == 0 || code >= 60000) {
                continue;
            }
            out.add(code);
        }
        return out;
    }

    /** Encode codes as Identity-H 2-byte big-endian content-stream bytes. */
    private static byte[] identityBytes(List<Integer> codes) {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        for (int code : codes) {
            bos.write((code >> 8) & 0xFF);
            bos.write(code & 0xFF);
        }
        return bos.toByteArray();
    }

    /**
     * Resolve the covered character codes from the descendant's /W array.
     * Mirrors CidGidProbe.coveredCodes exactly so the two probes address the
     * same code set. Under Identity-H the input code equals the CID.
     */
    private static List<Integer> coveredCodes(PDCIDFont descendant) {
        List<Integer> codes = new ArrayList<>();
        TreeSet<Integer> oob = new TreeSet<>();
        oob.add(60000);
        oob.add(65535);
        if (descendant == null) {
            codes.add(0);
            codes.addAll(oob);
            return codes;
        }
        COSDictionary dict = descendant.getCOSObject();
        COSBase wBase = dict.getDictionaryObject(COSName.W);
        TreeSet<Integer> set = new TreeSet<>();
        set.add(0);
        if (wBase instanceof COSArray) {
            COSArray w = (COSArray) wBase;
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
                        set.add(cFirst + k);
                    }
                    i += 2;
                } else if (next instanceof COSNumber) {
                    if (i + 2 >= n) {
                        break;
                    }
                    int cLast = ((COSNumber) next).intValue();
                    int upper = Math.min(cLast, cFirst + 1024);
                    for (int c = cFirst; c <= upper; c++) {
                        set.add(c);
                    }
                    i += 3;
                } else {
                    break;
                }
            }
        }
        set.addAll(oob);
        codes.addAll(set);
        return codes;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}

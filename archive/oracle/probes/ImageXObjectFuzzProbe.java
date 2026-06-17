import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Differential parse-/construction-leniency fuzz probe for IMAGE XObjects
 * ({@code /Subtype /Image}) and INLINE images ({@code BI}/{@code ID}/{@code EI}),
 * Apache PDFBox 3.0.7 (wave 1513, agent A).
 *
 * <p>Complements the existing image oracle suite — none of which fuzz the
 * <i>construction contract</i> over a malformed image dictionary. The
 * value-pinned probes (DctDecode / Ccitt / Jbig2 / Jpx / IccCmyk / Separation /
 * SoftMask / ColorKeyMask / SubByte / 16bit) all drive WELL-FORMED images and
 * compare decoded pixels; the inline probes (InlineImageDict / InlineCsResolve /
 * InlineFilterAbbrev / InlineImageKeyResolve) pin abbreviated-key precedence on
 * VALID dicts. This probe instead sweeps the MALFORMED / edge-case subset of the
 * shared {@code PDImage} accessor surface that both image shapes expose:
 * missing / mistyped {@code /Width} {@code /Height} {@code /BitsPerComponent};
 * {@code /ColorSpace} as name vs array vs missing vs unknown; {@code /Decode}
 * wrong-arity / out-of-range; {@code /ImageMask true} with/without {@code /Decode};
 * {@code /Mask} as colour-key array vs stream vs garbage; {@code /SMask};
 * {@code /Filter} standard names AND inline abbreviations
 * ({@code /AHx /A85 /LZW /Fl /RL /CCF /DCT}); {@code /DecodeParms};
 * {@code /Interpolate}; and — for inline images — the abbreviated key forms
 * ({@code /W /H /BPC /CS /F /DP /IM /D /I}) and the {@code BI}/{@code ID}/{@code EI}
 * token framing.
 *
 * <p>File-driven so the SAME bytes drive both sides (see XrefStreamFuzzProbe /
 * EncryptDictFuzzProbe for the manifest pattern). The pypdfbox sibling
 * (tests/pdmodel/graphics/image/oracle/test_image_fuzz_wave1513.py) writes a
 * deterministic corpus of minimal one-page PDFs into a directory plus a
 * {@code manifest.txt} (one line per case: {@code <kind> <name>}, where
 * {@code kind} is {@code XO} for an Image XObject case or {@code IN} for an
 * inline-image case, in order). For an {@code XO} case the fuzzed image is the
 * {@code /XObject /Im0} stream on page 0's resources; for an {@code IN} case it
 * is the first {@code BI} operator of page 0's content stream. Both libraries
 * load the identical PDF bytes off disk, so the construction contract is
 * directly comparable.
 *
 * <p>Output grammar — exactly one line per case, in manifest order:
 * <pre>
 *   CASE &lt;name&gt; ERR:&lt;ExcSimpleName&gt;
 *   CASE &lt;name&gt; w=&lt;int&gt; h=&lt;int&gt; bpc=&lt;int&gt; cs=&lt;tok&gt; mask=&lt;tok&gt; im=&lt;0|1&gt; \
 *        interp=&lt;0|1&gt; decode=&lt;tok&gt; filt=&lt;tok&gt; suffix=&lt;tok-or-null&gt;
 * </pre>
 * where the projection captures the observable construction contract:
 * <ul>
 *   <li>{@code w}/{@code h}/{@code bpc} — {@code getWidth/Height/BitsPerComponent}
 *       (each {@code -1} when absent / not a number; bpc is {@code 1} on a
 *       stencil regardless of the dict entry).</li>
 *   <li>{@code cs} — {@code getColorSpace().getName()}, or {@code NONE} when the
 *       accessor yields {@code null}, or {@code ERR} when it throws.</li>
 *   <li>{@code mask} — {@code none} (no {@code /Mask}), {@code key} (colour-key
 *       {@code COSArray}), {@code stream} (explicit-mask stream — XObject only),
 *       or {@code other} (a {@code /Mask} that is neither).</li>
 *   <li>{@code im} — {@code isStencil()} ({@code /ImageMask} / {@code /IM}).</li>
 *   <li>{@code interp} — {@code getInterpolate()}.</li>
 *   <li>{@code decode} — the {@code /Decode} ({@code /D}) array as
 *       comma-joined canonical numbers, or {@code none}.</li>
 *   <li>{@code filt} — filter names (abbreviations preserved) comma-joined, or
 *       {@code none}.</li>
 *   <li>{@code suffix} — {@code getSuffix()} (XObject) / inline suffix, or
 *       {@code null}.</li>
 * </ul>
 * An {@code ERR:<X>} line means resolving the image or one of the
 * unconditionally-read fields threw exception class X during construction /
 * projection (the colour-space {@code cs=ERR} token captures the common,
 * recoverable colour-space failure separately so the rest of the contract is
 * still comparable).
 */
public final class ImageXObjectFuzzProbe {

    static PrintStream out;

    static String num(COSBase v) {
        if (v instanceof COSInteger) {
            return Long.toString(((COSInteger) v).longValue());
        }
        if (v instanceof COSFloat) {
            return v.toString();
        }
        return "?";
    }

    static String decodeToken(COSBase v) {
        if (!(v instanceof COSArray)) {
            return "none";
        }
        COSArray a = (COSArray) v;
        if (a.size() == 0) {
            return "[]";
        }
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < a.size(); i++) {
            if (i > 0) {
                s.append(',');
            }
            s.append(num(a.get(i)));
        }
        return s.toString();
    }

    static String maskToken(COSBase m) {
        if (m == null) {
            return "none";
        }
        if (m instanceof COSArray) {
            return "key";
        }
        if (m instanceof org.apache.pdfbox.cos.COSStream) {
            return "stream";
        }
        return "other";
    }

    static String filtToken(COSBase f) {
        if (f instanceof COSName) {
            return ((COSName) f).getName();
        }
        if (f instanceof COSArray) {
            COSArray a = (COSArray) f;
            if (a.size() == 0) {
                return "none";
            }
            StringBuilder s = new StringBuilder();
            for (int i = 0; i < a.size(); i++) {
                if (i > 0) {
                    s.append(',');
                }
                COSBase e = a.get(i);
                s.append(e instanceof COSName ? ((COSName) e).getName() : "?");
            }
            return s.toString();
        }
        return "none";
    }

    static String csToken(java.util.concurrent.Callable<PDColorSpace> getter) {
        try {
            PDColorSpace cs = getter.call();
            return cs == null ? "NONE" : cs.getName();
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static void projectXObject(PDImageXObject img) {
        COSDictionary d = img.getCOSObject();
        StringBuilder sb = new StringBuilder();
        sb.append("w=").append(img.getWidth());
        sb.append(" h=").append(img.getHeight());
        sb.append(" bpc=").append(img.getBitsPerComponent());
        sb.append(" cs=").append(csToken(img::getColorSpace));
        sb.append(" mask=").append(maskToken(d.getDictionaryObject(COSName.MASK)));
        sb.append(" im=").append(img.isStencil() ? "1" : "0");
        sb.append(" interp=").append(img.getInterpolate() ? "1" : "0");
        sb.append(" decode=").append(decodeToken(d.getDictionaryObject(COSName.DECODE)));
        sb.append(" filt=").append(filtToken(d.getDictionaryObject(COSName.FILTER)));
        String suffix;
        try {
            suffix = img.getSuffix();
        } catch (Throwable t) {
            suffix = "ERR";
        }
        sb.append(" suffix=").append(suffix == null ? "null" : suffix);
        out.println(sb.toString());
    }

    static void projectInline(PDInlineImage img) {
        COSDictionary d = img.getCOSObject();
        StringBuilder sb = new StringBuilder();
        sb.append("w=").append(img.getWidth());
        sb.append(" h=").append(img.getHeight());
        sb.append(" bpc=").append(img.getBitsPerComponent());
        sb.append(" cs=").append(csToken(img::getColorSpace));
        sb.append(" mask=").append(maskToken(d.getDictionaryObject(COSName.MASK)));
        sb.append(" im=").append(img.isStencil() ? "1" : "0");
        sb.append(" interp=").append(img.getInterpolate() ? "1" : "0");
        // Inline /Decode resolves via /D then /Decode.
        COSBase dec = d.getDictionaryObject(COSName.D, COSName.DECODE);
        sb.append(" decode=").append(decodeToken(dec));
        COSBase filt = d.getDictionaryObject(COSName.F, COSName.FILTER);
        sb.append(" filt=").append(filtToken(filt));
        String suffix;
        try {
            suffix = img.getSuffix();
        } catch (Throwable t) {
            suffix = "ERR";
        }
        sb.append(" suffix=").append(suffix == null ? "null" : suffix);
        out.println(sb.toString());
    }

    static void runXObject(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            COSName im0 = COSName.getPDFName("Im0");
            PDXObject xobj = res.getXObject(im0);
            if (!(xobj instanceof PDImageXObject)) {
                out.println("CASE " + name + " ERR:NotImageXObject");
                return;
            }
            out.print("CASE " + name + " ");
            projectXObject((PDImageXObject) xobj);
        } catch (Throwable t) {
            out.println("CASE " + name + " ERR:" + t.getClass().getSimpleName());
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignore) {
                    // best effort
                }
            }
        }
    }

    static void runInline(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            byte[] content = page.getContents().readAllBytes();
            PDFStreamParser parser = new PDFStreamParser(content);
            List<Object> tokens = parser.parse();
            Operator bi = null;
            for (Object tok : tokens) {
                if (tok instanceof Operator
                        && "BI".equals(((Operator) tok).getName())) {
                    bi = (Operator) tok;
                    break;
                }
            }
            if (bi == null) {
                out.println("CASE " + name + " ERR:NoBI");
                return;
            }
            COSDictionary params = bi.getImageParameters();
            byte[] data = bi.getImageData();
            PDInlineImage img =
                    new PDInlineImage(params, data == null ? new byte[0] : data, res);
            out.print("CASE " + name + " ");
            projectInline(img);
        } catch (Throwable t) {
            out.println("CASE " + name + " ERR:" + t.getClass().getSimpleName());
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignore) {
                    // best effort
                }
            }
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] lines =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        for (String raw : lines) {
            String line = raw.trim();
            if (line.isEmpty()) {
                continue;
            }
            int sp = line.indexOf(' ');
            String kind = line.substring(0, sp);
            String name = line.substring(sp + 1).trim();
            if ("XO".equals(kind)) {
                runXObject(dir, name);
            } else {
                runInline(dir, name);
            }
        }
    }
}

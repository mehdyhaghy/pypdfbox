import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: build ~25-35 small documents with EDGE CONTENT entirely in
 * memory (NOT loaded from disk), full-save each one UNCOMPRESSED through Apache
 * PDFBox 3.0.7's COSWriter, reload the saved bytes, and project a STABLE
 * STRUCTURAL SHAPE — never exact bytes. Byte-identical output is not required;
 * what a port must reproduce is the structural validity + the key trailer
 * fields after a round-trip.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CosWriterSaveFuzzProbe <caseName>
 *
 * Output (UTF-8, LF-terminated, key=value):
 *   ok=true|false              -- did the save + reload round-trip succeed
 *   objcount=<N>               -- # of indirect objects in the reloaded xref table
 *   size=<N>                   -- trailer /Size after reload
 *   has_root=true|false        -- trailer carries a /Root reference
 *   has_info=true|false        -- trailer carries an /Info reference
 *   has_prev=true|false        -- trailer carries a /Prev (should be false on full save)
 *   xref_stream=true|false     -- output used a /Type /XRef stream (false = classic table)
 *   roundtrip_str=<decoded>    -- (string cases) the COSString value read back, hex-escaped
 *
 * The compared shape is numbering-INDEPENDENT and reader-deterministic so a port
 * can assert the same facts after its own uncompressed full save.
 */
public final class CosWriterSaveFuzzProbe {

    public static void main(String[] args) throws Exception {
        String name = args.length > 0 ? args[0] : "empty";
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        byte[] saved;
        try {
            saved = build(name);
        } catch (Exception ex) {
            out.println("ok=false");
            out.println("error=" + ex.getClass().getSimpleName());
            return;
        }

        try (PDDocument pd = Loader.loadPDF(saved)) {
            COSDocument cos = pd.getDocument();
            COSDictionary trailer = cos.getTrailer();

            int objcount = cos.getXrefTable().size();
            long size = trailer.getLong(COSName.SIZE);
            boolean hasRoot = trailer.getItem(COSName.ROOT) != null;
            boolean hasInfo = trailer.getItem(COSName.INFO) != null;
            boolean hasPrev = trailer.getItem(COSName.PREV) != null;

            String s = new String(saved, "ISO-8859-1");
            boolean xrefStream = s.contains("/Type /XRef") || s.contains("/Type/XRef");

            out.println("ok=true");
            out.println("objcount=" + objcount);
            out.println("size=" + size);
            out.println("has_root=" + hasRoot);
            out.println("has_info=" + hasInfo);
            out.println("has_prev=" + hasPrev);
            out.println("xref_stream=" + xrefStream);

            // For string-escape cases: read the probe string back from the catalog.
            COSBase rootBase = trailer.getDictionaryObject(COSName.ROOT);
            if (rootBase instanceof COSDictionary) {
                COSDictionary root = (COSDictionary) rootBase;
                COSBase probe = root.getDictionaryObject(COSName.getPDFName("ProbeStr"));
                if (probe instanceof COSString) {
                    out.println("roundtrip_str=" + hexEscape(((COSString) probe).getBytes()));
                }
                COSBase nested = root.getDictionaryObject(COSName.getPDFName("Nested"));
                if (nested != null) {
                    out.println("nested_depth=" + depth(nested, 0));
                }
            }
        }
    }

    /** Build + save an edge-case document, returning the saved bytes. */
    private static byte[] build(String name) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            COSDocument cos = doc.getDocument();
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();

            switch (name) {
                case "empty":
                    break;
                case "one_page":
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    break;
                case "many_pages":
                    for (int i = 0; i < 8; i++) {
                        doc.addPage(new PDPage(PDRectangle.LETTER));
                    }
                    break;
                case "with_info": {
                    doc.getDocumentInformation().setTitle("Edge");
                    doc.getDocumentInformation().setAuthor("Fuzz");
                    break;
                }
                case "str_parens":
                    catalog.setItem("ProbeStr", new COSString("a(b)c"));
                    break;
                case "str_backslash":
                    catalog.setItem("ProbeStr", new COSString("a\\b"));
                    break;
                case "str_newline":
                    catalog.setItem("ProbeStr", new COSString("line1\nline2\r\t"));
                    break;
                case "str_binary":
                    catalog.setItem("ProbeStr",
                            new COSString(new byte[] {0, 1, 2, (byte) 255, (byte) 128}));
                    break;
                case "str_empty":
                    catalog.setItem("ProbeStr", new COSString(""));
                    break;
                case "str_unbalanced_parens":
                    catalog.setItem("ProbeStr", new COSString("a)b(c"));
                    break;
                case "nested_arrays": {
                    COSArray a = new COSArray();
                    COSArray b = new COSArray();
                    COSArray c = new COSArray();
                    c.add(COSInteger.get(42));
                    b.add(c);
                    a.add(b);
                    catalog.setItem("Nested", a);
                    break;
                }
                case "nested_dicts": {
                    COSDictionary d1 = new COSDictionary();
                    COSDictionary d2 = new COSDictionary();
                    d2.setInt("Leaf", 7);
                    d1.setItem("Inner", d2);
                    catalog.setItem("Nested", d1);
                    break;
                }
                case "deep_nested": {
                    COSBase cur = COSInteger.get(1);
                    for (int i = 0; i < 12; i++) {
                        COSArray a = new COSArray();
                        a.add(cur);
                        cur = a;
                    }
                    catalog.setItem("Nested", cur);
                    break;
                }
                case "indirect_int": {
                    COSInteger ind = COSInteger.get(99);
                    COSObject obj = new COSObject(ind);
                    cos.getXrefTable().put(new COSObjectKey(9999, 0), 0L);
                    catalog.setItem("ProbeRef", obj);
                    break;
                }
                case "self_ref_array": {
                    COSArray a = new COSArray();
                    a.add(catalog);
                    catalog.setItem("BackRef", a);
                    break;
                }
                case "many_strings": {
                    COSArray a = new COSArray();
                    for (int i = 0; i < 20; i++) {
                        a.add(new COSString("s" + i));
                    }
                    catalog.setItem("Strs", a);
                    break;
                }
                case "bool_null_mix": {
                    COSArray a = new COSArray();
                    a.add(org.apache.pdfbox.cos.COSBoolean.TRUE);
                    a.add(org.apache.pdfbox.cos.COSBoolean.FALSE);
                    a.add(org.apache.pdfbox.cos.COSNull.NULL);
                    catalog.setItem("Mix", a);
                    break;
                }
                case "float_values": {
                    COSArray a = new COSArray();
                    a.add(new org.apache.pdfbox.cos.COSFloat(1.5f));
                    a.add(new org.apache.pdfbox.cos.COSFloat(-0.25f));
                    a.add(new org.apache.pdfbox.cos.COSFloat(0.0f));
                    catalog.setItem("Floats", a);
                    break;
                }
                case "name_with_specials": {
                    catalog.setItem(COSName.getPDFName("A#B C"),
                            COSName.getPDFName("val/ue"));
                    break;
                }
                case "reload_resave": {
                    // Build, save, reload, then re-save: a re-saved doc.
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    ByteArrayOutputStream first = new ByteArrayOutputStream();
                    doc.save(first, CompressParameters.NO_COMPRESSION);
                    try (PDDocument re = Loader.loadPDF(first.toByteArray())) {
                        ByteArrayOutputStream second = new ByteArrayOutputStream();
                        re.save(second, CompressParameters.NO_COMPRESSION);
                        return second.toByteArray();
                    }
                }
                case "incremental_then_full": {
                    // Save, reload, incrementally append, reload, full-save.
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    ByteArrayOutputStream first = new ByteArrayOutputStream();
                    doc.save(first, CompressParameters.NO_COMPRESSION);
                    byte[] base = first.toByteArray();
                    byte[] incremented;
                    try (PDDocument inc = Loader.loadPDF(base)) {
                        inc.getDocumentCatalog().getCOSObject()
                                .setNeedToBeUpdated(true);
                        inc.getDocumentInformation().setTitle("Appended");
                        ByteArrayOutputStream incOut = new ByteArrayOutputStream();
                        inc.saveIncremental(incOut);
                        incremented = incOut.toByteArray();
                    }
                    try (PDDocument re = Loader.loadPDF(incremented)) {
                        ByteArrayOutputStream full = new ByteArrayOutputStream();
                        re.save(full, CompressParameters.NO_COMPRESSION);
                        return full.toByteArray();
                    }
                }
                case "large_size_hint": {
                    // Force a high existing object number so /Size is large.
                    cos.getXrefTable().put(new COSObjectKey(50000, 0), 0L);
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    break;
                }
                default:
                    throw new IllegalArgumentException("unknown case: " + name);
            }

            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.save(bos, CompressParameters.NO_COMPRESSION);
            return bos.toByteArray();
        }
    }

    private static int depth(COSBase base, int d) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        if (base instanceof COSArray) {
            COSArray a = (COSArray) base;
            int max = d;
            for (int i = 0; i < a.size(); i++) {
                max = Math.max(max, depth(a.get(i), d + 1));
            }
            return max;
        }
        if (base instanceof COSDictionary) {
            COSDictionary di = (COSDictionary) base;
            int max = d;
            for (COSName k : di.keySet()) {
                max = Math.max(max, depth(di.getDictionaryObject(k), d + 1));
            }
            return max;
        }
        return d;
    }

    private static String hexEscape(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}

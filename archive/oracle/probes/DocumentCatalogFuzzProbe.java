import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PageLayout;
import org.apache.pdfbox.pdmodel.PageMode;
import org.apache.pdfbox.pdmodel.common.PDDestinationOrAction;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo;
import org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent;

/**
 * In-memory differential fuzz probe for {@link PDDocumentCatalog} accessors,
 * Apache PDFBox 3.0.7 (wave 1547, agent B).
 *
 * <p>Distinct from the file-driven {@code CatalogFuzzProbe} (wave 1515): that
 * probe round-trips each fuzzed catalog through {@code save} +
 * {@code Loader.loadPDF}, so the parser/writer can normalise or strip a
 * malformed value before the accessor ever sees it. This probe instead
 * constructs {@code PDDocumentCatalog} DIRECTLY over a hand-built (and often
 * malformed) root {@link COSDictionary} via the protected
 * {@code PDDocumentCatalog(PDDocument, COSDictionary)} constructor (reflected),
 * so each accessor's own leniency is what is observed — no round-trip in the
 * way.
 *
 * <p>It also extends the accessor surface beyond wave 1515 by projecting
 * {@code getOCProperties}, {@code getMetadata}, and {@code getOutputIntents}
 * (the latter's per-entry {@code (COSDictionary)} cast is a known divergence:
 * upstream throws on a non-dict array entry where pypdfbox skips it).
 *
 * <p>The fuzz corpus is hard-coded in BOTH this probe and its pypdfbox sibling
 * ({@code tests/pdmodel/oracle/test_document_catalog_fuzz_wave1547.py}) so the
 * two stacks build byte-identical in-memory dicts. No external input: this
 * probe takes no arguments and emits one framed line per case in a fixed order.
 *
 * <p>Line grammar (one per case)::
 *
 * <pre>
 *   CASE &lt;name&gt; version=&lt;str|null|ERR:X&gt; layout=&lt;enum|ERR:X&gt; mode=&lt;enum|ERR:X&gt; openaction=&lt;cls|null|ERR:X&gt; lang=&lt;str|null|ERR:X&gt; markinfo=&lt;cls|null|ERR:X&gt; marked=&lt;0|1|ERR:X&gt; metadata=&lt;cls|null|ERR:X&gt; ocprops=&lt;cls|null|ERR:X&gt; oi=&lt;int|ERR:X&gt; struct=&lt;cls|null|ERR:X&gt; names=&lt;cls|null|ERR:X&gt; dests=&lt;cls|null|ERR:X&gt; outline=&lt;cls|null|ERR:X&gt; acro=&lt;cls|null|ERR:X&gt;
 * </pre>
 *
 * <p>{@code layout} / {@code mode} are the DEFAULT-applying upstream getters
 * ({@code getPageLayout().stringValue()} / {@code getPageMode().stringValue()})
 * — never null. {@code oi} is the SIZE of {@code getOutputIntents()} (or an
 * ERR token). All other cells report the resolved wrapper's simple class name,
 * "null", or "ERR:&lt;ExcSimpleName&gt;".
 */
public final class DocumentCatalogFuzzProbe {

    static PrintStream out;

    static final COSName N_VERSION = COSName.getPDFName("Version");
    static final COSName N_LANG = COSName.getPDFName("Lang");
    static final COSName N_PAGE_LAYOUT = COSName.getPDFName("PageLayout");
    static final COSName N_PAGE_MODE = COSName.getPDFName("PageMode");
    static final COSName N_OPEN_ACTION = COSName.getPDFName("OpenAction");
    static final COSName N_MARK_INFO = COSName.getPDFName("MarkInfo");
    static final COSName N_METADATA = COSName.getPDFName("Metadata");
    static final COSName N_OC = COSName.getPDFName("OCProperties");
    static final COSName N_OI = COSName.getPDFName("OutputIntents");
    static final COSName N_STRUCT = COSName.getPDFName("StructTreeRoot");
    static final COSName N_NAMES = COSName.getPDFName("Names");
    static final COSName N_DESTS = COSName.getPDFName("Dests");
    static final COSName N_OUTLINES = COSName.getPDFName("Outlines");
    static final COSName N_ACROFORM = COSName.getPDFName("AcroForm");
    static final COSName N_S = COSName.getPDFName("S");
    static final COSName N_TYPE = COSName.getPDFName("Type");
    static final COSName N_MARKED = COSName.getPDFName("Marked");
    static final COSName N_D = COSName.getPDFName("D");
    static final COSName N_FIELDS = COSName.getPDFName("Fields");

    static String exc(Throwable e) {
        // Unwrap reflective wrappers so the simple-name token matches the real
        // exception the accessor would throw outside reflection.
        if (e instanceof java.lang.reflect.InvocationTargetException
                && e.getCause() != null) {
            e = e.getCause();
        }
        if (e instanceof java.io.IOException) {
            return "ERR:IOException";
        }
        return "ERR:" + e.getClass().getSimpleName();
    }

    static String cls(Object o) {
        return o == null ? "null" : o.getClass().getSimpleName();
    }

    static String version(PDDocumentCatalog cat) {
        try {
            String v = cat.getVersion();
            return v == null ? "null" : v;
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String layout(PDDocumentCatalog cat) {
        try {
            PageLayout l = cat.getPageLayout();
            return l == null ? "null" : l.stringValue();
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String mode(PDDocumentCatalog cat) {
        try {
            PageMode m = cat.getPageMode();
            return m == null ? "null" : m.stringValue();
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String openAction(PDDocumentCatalog cat) {
        try {
            PDDestinationOrAction oa = cat.getOpenAction();
            return oa == null ? "null" : oa.getClass().getSimpleName();
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String lang(PDDocumentCatalog cat) {
        try {
            String l = cat.getLanguage();
            return l == null ? "null" : l;
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String markInfo(PDDocumentCatalog cat) {
        try {
            PDMarkInfo mi = cat.getMarkInfo();
            return mi == null ? "null" : mi.getClass().getSimpleName();
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String marked(PDDocumentCatalog cat) {
        try {
            PDMarkInfo mi = cat.getMarkInfo();
            return mi != null && mi.isMarked() ? "1" : "0";
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String metadata(PDDocumentCatalog cat) {
        try {
            return cls(cat.getMetadata());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String ocProps(PDDocumentCatalog cat) {
        try {
            return cls(cat.getOCProperties());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String outputIntents(PDDocumentCatalog cat) {
        try {
            List<PDOutputIntent> oi = cat.getOutputIntents();
            return Integer.toString(oi.size());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String struct(PDDocumentCatalog cat) {
        try {
            return cls(cat.getStructureTreeRoot());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String names(PDDocumentCatalog cat) {
        try {
            return cls(cat.getNames());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String dests(PDDocumentCatalog cat) {
        try {
            return cls(cat.getDests());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String outline(PDDocumentCatalog cat) {
        try {
            return cls(cat.getDocumentOutline());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String acro(PDDocumentCatalog cat) {
        try {
            return cls(cat.getAcroForm(null));
        } catch (Throwable e) {
            return exc(e);
        }
    }

    // ----------------------------------------------------------- corpus builders

    static COSDictionary action(String subType) {
        COSDictionary d = new COSDictionary();
        d.setItem(N_TYPE, COSName.getPDFName("Action"));
        if (subType != null) {
            d.setItem(N_S, COSName.getPDFName(subType));
        }
        d.setItem(N_D, new COSArray());
        return d;
    }

    static COSDictionary markInfoDict(boolean marked) {
        COSDictionary d = new COSDictionary();
        d.setItem(N_TYPE, COSName.getPDFName("MarkInfo"));
        d.setBoolean(N_MARKED, marked);
        return d;
    }

    static COSDictionary acroFormDict() {
        COSDictionary d = new COSDictionary();
        d.setItem(N_FIELDS, new COSArray());
        return d;
    }

    static COSStream metadataStream(PDDocument doc) {
        COSStream s = doc.getDocument().createCOSStream();
        s.setItem(N_TYPE, COSName.getPDFName("Metadata"));
        return s;
    }

    static COSArray destArray() {
        // Self-contained explicit destination [<pageDict> /Fit]; no real page
        // object needed since the catalog accessor only wraps the array shape.
        COSArray arr = new COSArray();
        COSDictionary pageDict = new COSDictionary();
        pageDict.setItem(N_TYPE, COSName.getPDFName("Page"));
        arr.add(pageDict);
        arr.add(COSName.getPDFName("Fit"));
        return arr;
    }

    static COSArray outputIntentArr(boolean withBadEntry) {
        COSArray arr = new COSArray();
        COSDictionary oi = new COSDictionary();
        oi.setItem(N_TYPE, COSName.getPDFName("OutputIntent"));
        oi.setItem(COSName.getPDFName("S"), COSName.getPDFName("GTS_PDFA1"));
        arr.add(oi);
        if (withBadEntry) {
            arr.add(COSName.getPDFName("NotADict"));
        }
        return arr;
    }

    // --------------------------------------------------------------------- main

    static Constructor<PDDocumentCatalog> ctor;

    static PDDocumentCatalog build(PDDocument doc, COSDictionary root)
            throws Exception {
        // Reflect the protected (PDDocument, COSDictionary) constructor so the
        // catalog wraps our hand-built root with no save/load normalisation.
        return ctor.newInstance(doc, root);
    }

    static void runCase(PDDocument doc, String name, COSDictionary root) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            // Ensure /Type /Catalog so the constructor's own fixup is a no-op
            // and never mutates the dict out from under the fuzzed value.
            if (!(root.getDictionaryObject(N_TYPE) instanceof COSName)) {
                root.setItem(N_TYPE, COSName.getPDFName("Catalog"));
            }
            PDDocumentCatalog cat = build(doc, root);
            sb.append("version=").append(version(cat));
            sb.append(" layout=").append(layout(cat));
            sb.append(" mode=").append(mode(cat));
            sb.append(" openaction=").append(openAction(cat));
            sb.append(" lang=").append(lang(cat));
            sb.append(" markinfo=").append(markInfo(cat));
            sb.append(" marked=").append(marked(cat));
            sb.append(" metadata=").append(metadata(cat));
            sb.append(" ocprops=").append(ocProps(cat));
            sb.append(" oi=").append(outputIntents(cat));
            sb.append(" struct=").append(struct(cat));
            sb.append(" names=").append(names(cat));
            sb.append(" dests=").append(dests(cat));
            sb.append(" outline=").append(outline(cat));
            sb.append(" acro=").append(acro(cat));
        } catch (Throwable e) {
            sb.append("BUILD:").append(e.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        ctor = (Constructor<PDDocumentCatalog>)
                PDDocumentCatalog.class.getDeclaredConstructor(
                        PDDocument.class, COSDictionary.class);
        ctor.setAccessible(true);

        try (PDDocument doc = new PDDocument()) {
            // ---- bare catalog: every probed entry absent ----
            runCase(doc, "bare", new COSDictionary());

            // ---- /Version: name / string / float / int / array ----
            runCase(doc, "version_name_17", root(N_VERSION, COSName.getPDFName("1.7")));
            runCase(doc, "version_string_15", root(N_VERSION, new COSString("1.5")));
            runCase(doc, "version_float", root(N_VERSION, new COSFloat(2.0f)));
            runCase(doc, "version_int", root(N_VERSION, COSInteger.get(2)));
            runCase(doc, "version_array", root(N_VERSION, new COSArray()));

            // ---- /PageLayout: valid / unknown / wrong-type / (missing=bare) ----
            for (String lay : new String[] {
                "SinglePage", "OneColumn", "TwoColumnLeft", "TwoColumnRight",
                "TwoPageLeft", "TwoPageRight"
            }) {
                runCase(doc, "layout_" + lay, root(N_PAGE_LAYOUT, COSName.getPDFName(lay)));
            }
            runCase(doc, "layout_unknown", root(N_PAGE_LAYOUT, COSName.getPDFName("Sideways")));
            runCase(doc, "layout_string", root(N_PAGE_LAYOUT, new COSString("OneColumn")));
            runCase(doc, "layout_int", root(N_PAGE_LAYOUT, COSInteger.get(1)));

            // ---- /PageMode: valid / unknown / wrong-type ----
            for (String m : new String[] {
                "UseNone", "UseOutlines", "UseThumbs", "FullScreen",
                "UseOC", "UseAttachments"
            }) {
                runCase(doc, "mode_" + m, root(N_PAGE_MODE, COSName.getPDFName(m)));
            }
            runCase(doc, "mode_unknown", root(N_PAGE_MODE, COSName.getPDFName("UseXfa")));
            runCase(doc, "mode_string", root(N_PAGE_MODE, new COSString("UseThumbs")));

            // ---- /OpenAction: action (known/unknown/D-only) / dest / wrong ----
            runCase(doc, "openaction_goto", root(N_OPEN_ACTION, action("GoTo")));
            runCase(doc, "openaction_uri", root(N_OPEN_ACTION, action("URI")));
            runCase(doc, "openaction_unknown_s", root(N_OPEN_ACTION, action("Bogus")));
            runCase(doc, "openaction_d_only", root(N_OPEN_ACTION, action(null)));
            runCase(doc, "openaction_dest", root(N_OPEN_ACTION, destArray()));
            runCase(doc, "openaction_name", root(N_OPEN_ACTION, COSName.getPDFName("Foo")));
            runCase(doc, "openaction_string", root(N_OPEN_ACTION, new COSString("Foo")));

            // ---- /Lang: string / name / int ----
            runCase(doc, "lang_string", root(N_LANG, new COSString("en-US")));
            runCase(doc, "lang_name", root(N_LANG, COSName.getPDFName("en-US")));
            runCase(doc, "lang_int", root(N_LANG, COSInteger.get(1)));

            // ---- /MarkInfo: marked / unmarked / wrong-type ----
            runCase(doc, "markinfo_marked", root(N_MARK_INFO, markInfoDict(true)));
            runCase(doc, "markinfo_unmarked", root(N_MARK_INFO, markInfoDict(false)));
            runCase(doc, "markinfo_array", root(N_MARK_INFO, new COSArray()));

            // ---- /Metadata: stream / dict (wrong) / name (wrong) ----
            runCase(doc, "metadata_stream", root(N_METADATA, metadataStream(doc)));
            runCase(doc, "metadata_dict", root(N_METADATA, new COSDictionary()));
            runCase(doc, "metadata_name", root(N_METADATA, COSName.getPDFName("X")));

            // ---- /OCProperties: dict / array (wrong) ----
            runCase(doc, "ocprops_dict", root(N_OC, new COSDictionary()));
            runCase(doc, "ocprops_array", root(N_OC, new COSArray()));

            // ---- /OutputIntents: clean array / array+bad entry / dict (wrong) ----
            runCase(doc, "oi_clean", root(N_OI, outputIntentArr(false)));
            runCase(doc, "oi_bad_entry", root(N_OI, outputIntentArr(true)));
            runCase(doc, "oi_dict", root(N_OI, new COSDictionary()));

            // ---- /StructTreeRoot, /Names, /Dests, /Outlines, /AcroForm ----
            runCase(doc, "struct_dict", root(N_STRUCT, new COSDictionary()));
            runCase(doc, "struct_array", root(N_STRUCT, new COSArray()));
            runCase(doc, "names_dict", root(N_NAMES, new COSDictionary()));
            runCase(doc, "names_array", root(N_NAMES, new COSArray()));
            runCase(doc, "dests_dict", root(N_DESTS, new COSDictionary()));
            runCase(doc, "dests_string", root(N_DESTS, new COSString("x")));
            runCase(doc, "outline_dict", root(N_OUTLINES, new COSDictionary()));
            runCase(doc, "outline_int", root(N_OUTLINES, COSInteger.get(0)));
            runCase(doc, "acro_dict", root(N_ACROFORM, acroFormDict()));
            runCase(doc, "acro_name", root(N_ACROFORM, COSName.getPDFName("Form")));
        }
    }

    static COSDictionary root(COSName key, COSBase value) {
        COSDictionary d = new COSDictionary();
        d.setItem(key, value);
        return d;
    }
}

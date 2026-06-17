import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PageLayout;
import org.apache.pdfbox.pdmodel.PageMode;
import org.apache.pdfbox.pdmodel.common.PDDestinationOrAction;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo;

/**
 * Differential fuzz probe for {@link PDDocumentCatalog} accessor / enum
 * leniency over a MALFORMED catalog (root) dictionary, Apache PDFBox 3.0.7
 * (wave 1515, agent D).
 *
 * <p>Complements the well-formed catalog oracle suite
 * ({@code test_catalog_oracle}, {@code test_catalog_meta_oracle},
 * {@code test_catalog_page_enum_oracle}, {@code test_catalog_version_oracle},
 * {@code test_viewer_prefs_oracle}) — none of which exercise the malformed /
 * mistyped catalog subset this probe targets:
 *
 * <ul>
 *   <li>{@code /Version} as a name vs string vs number vs missing
 *       ({@code getVersion} delegates to
 *       {@code COSDictionary.getNameAsString}, which accepts a COSName or a
 *       COSString and returns null otherwise);</li>
 *   <li>{@code /PageLayout} enum sweep (SinglePage / OneColumn /
 *       TwoColumnLeft / TwoColumnRight / TwoPageLeft / TwoPageRight / unknown /
 *       wrong-type / missing) — {@code getPageLayout} is DEFAULT-applying:
 *       absent / unknown / wrong-type all fold to SinglePage;</li>
 *   <li>{@code /PageMode} enum sweep (UseNone / UseOutlines / UseThumbs /
 *       FullScreen / UseOC / UseAttachments / unknown / wrong-type / missing)
 *       — {@code getPageMode} folds absent / unknown / wrong-type to
 *       UseNone;</li>
 *   <li>{@code /OpenAction} as an action dict (recognised /S, unknown /S,
 *       /D-only shorthand), a destination array, and a wrong-type value;</li>
 *   <li>{@code /Lang} string vs wrong-type vs missing;</li>
 *   <li>{@code /MarkInfo} dict vs wrong-type (and the /Marked flag inside);
 *       </li>
 *   <li>presence / wrong-type of {@code /PageLabels} {@code /ViewerPreferences}
 *       {@code /Names} {@code /Dests} {@code /Outlines} {@code /StructTreeRoot}
 *       {@code /AcroForm} {@code /URI}.</li>
 * </ul>
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/oracle/test_catalog_fuzz_wave1515.py) writes a deterministic
 * corpus of one-page PDFs whose catalog (root) dictionary IS the fuzzed dict,
 * plus a {@code manifest.txt} (one case name per line, in order) into a tmp
 * dir. This probe loads each {@code <case>.pdf}, resolves the document
 * catalog, and projects a stable framed line. Both sides read the exact same
 * bytes on disk.
 *
 * <p>Line grammar (one per case, manifest order):
 *
 * <pre>
 *   CASE &lt;name&gt; version=&lt;str|null|ERR:X&gt; layout=&lt;enum|ERR:X&gt; mode=&lt;enum|ERR:X&gt; openaction=&lt;cls|null|ERR:X&gt; lang=&lt;str|null|ERR:X&gt; markinfo=&lt;cls|null|ERR:X&gt; marked=&lt;0|1|ERR:X&gt; labels=&lt;cls|null|ERR:X&gt; vprefs=&lt;cls|null|ERR:X&gt; names=&lt;cls|null|ERR:X&gt; dests=&lt;cls|null|ERR:X&gt; outline=&lt;cls|null|ERR:X&gt; struct=&lt;cls|null|ERR:X&gt; acro=&lt;cls|null|ERR:X&gt; uri=&lt;cls|null|ERR:X&gt;
 * </pre>
 *
 * <p>{@code layout} / {@code mode} are the DEFAULT-applying upstream getters
 * ({@code getPageLayout().stringValue()} / {@code getPageMode().stringValue()})
 * — never null. The pypdfbox sibling compares them against
 * {@code get_page_layout_or_default()} / {@code get_page_mode_or_default()}
 * (the upstream-compatible default-applying reads). All other cells report the
 * resolved wrapper's simple class name, "null", or "ERR:&lt;ExcSimpleName&gt;".
 */
public final class CatalogFuzzProbe {

    static PrintStream out;

    static String exc(Exception e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    static String version(PDDocumentCatalog cat) {
        try {
            String v = cat.getVersion();
            return v == null ? "null" : v;
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String layout(PDDocumentCatalog cat) {
        try {
            PageLayout l = cat.getPageLayout();
            return l == null ? "null" : l.stringValue();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String mode(PDDocumentCatalog cat) {
        try {
            PageMode m = cat.getPageMode();
            return m == null ? "null" : m.stringValue();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String openAction(PDDocumentCatalog cat) {
        try {
            PDDestinationOrAction oa = cat.getOpenAction();
            return oa == null ? "null" : oa.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String lang(PDDocumentCatalog cat) {
        try {
            String l = cat.getLanguage();
            return l == null ? "null" : l;
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String markInfo(PDDocumentCatalog cat) {
        try {
            PDMarkInfo mi = cat.getMarkInfo();
            return mi == null ? "null" : mi.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String marked(PDDocumentCatalog cat) {
        try {
            PDMarkInfo mi = cat.getMarkInfo();
            return mi != null && mi.isMarked() ? "1" : "0";
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String cls(Object o) {
        return o == null ? "null" : o.getClass().getSimpleName();
    }

    static String labels(PDDocumentCatalog cat) {
        try {
            return cls(cat.getPageLabels());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String vprefs(PDDocumentCatalog cat) {
        try {
            return cls(cat.getViewerPreferences());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String names(PDDocumentCatalog cat) {
        try {
            return cls(cat.getNames());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String dests(PDDocumentCatalog cat) {
        try {
            return cls(cat.getDests());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String outline(PDDocumentCatalog cat) {
        try {
            return cls(cat.getDocumentOutline());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String struct(PDDocumentCatalog cat) {
        try {
            return cls(cat.getStructureTreeRoot());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String acro(PDDocumentCatalog cat) {
        try {
            return cls(cat.getAcroForm(null));
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String uri(PDDocumentCatalog cat) {
        try {
            return cls(cat.getURI());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            sb.append("version=").append(version(cat));
            sb.append(" layout=").append(layout(cat));
            sb.append(" mode=").append(mode(cat));
            sb.append(" openaction=").append(openAction(cat));
            sb.append(" lang=").append(lang(cat));
            sb.append(" markinfo=").append(markInfo(cat));
            sb.append(" marked=").append(marked(cat));
            sb.append(" labels=").append(labels(cat));
            sb.append(" vprefs=").append(vprefs(cat));
            sb.append(" names=").append(names(cat));
            sb.append(" dests=").append(dests(cat));
            sb.append(" outline=").append(outline(cat));
            sb.append(" struct=").append(struct(cat));
            sb.append(" acro=").append(acro(cat));
            sb.append(" uri=").append(uri(cat));
        } catch (Exception e) {
            sb.append("LOAD:").append(e.getClass().getSimpleName());
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}

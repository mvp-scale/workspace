import de.uni_mannheim.minie.MinIE;
import de.uni_mannheim.minie.annotation.AnnotatedProposition;
import de.uni_mannheim.utils.coreNLP.CoreNLPUtils;
import edu.stanford.nlp.pipeline.StanfordCoreNLP;
import java.io.*;
public class RunMinie {
  public static void main(String[] a) throws Exception {
    StanfordCoreNLP p = CoreNLPUtils.StanfordDepNNParser();
    BufferedReader r = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
    String l; long t0 = System.nanoTime(); int n = 0;
    while ((l = r.readLine()) != null) {
      String[] f = l.split("\t", 2);
      long s = System.nanoTime();
      MinIE m = new MinIE(f[1], p, MinIE.Mode.SAFE);
      System.out.println("#" + f[0] + "\t" + (System.nanoTime()-s)/1000000 + "ms\t" + f[1]);
      for (AnnotatedProposition ap : m.getPropositions()) System.out.println("  " + ap.toString().replace("\n"," "));
      n++;
    }
    System.err.println("sentences " + n + " total ms " + (System.nanoTime()-t0)/1000000);
  }
}

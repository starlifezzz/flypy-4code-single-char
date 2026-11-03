/* verify.c —— 用 librime 把一批编码逐键回放，统计有多少四码没能直接上屏。
 *
 * 用法: verify <shared_data_dir> <user_data_dir> < codes.txt
 * 输出: 每个多候选码一行：
 *         MULTI<TAB><code><TAB><候选数><TAB>候选1|候选2|候选3
 *       末行：
 *         TOTAL=<n> MULTI=<n> COMMITTED=<n>
 *
 * 判据：一次 process_key 回放完整个编码后，若 rime_get_commit() 有值，
 *       说明「停手即上屏」；否则看菜单还剩几个候选。
 */
#include <rime_api.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: %s <shared_data_dir> <user_data_dir> < codes.txt\n", argv[0]);
    return 2;
  }

  RimeApi *rime = rime_get_api();

  RIME_STRUCT(RimeTraits, traits);
  traits.shared_data_dir = argv[1];
  traits.user_data_dir = argv[2];
  traits.log_dir = "/tmp";
  traits.distribution_name = "flypy4-verify";
  traits.distribution_code_name = "flypy4";
  traits.distribution_version = "1";
  traits.app_name = "rime.flypy4";

  rime->setup(&traits);
  rime->initialize(&traits);
  if (rime->start_maintenance(True)) {
    rime->join_maintenance_thread();
  }

  RimeSessionId session = rime->create_session();
  if (!session) {
    fprintf(stderr, "create_session 失败：检查 user_data_dir 里有没有 flypy.schema.yaml\n");
    return 1;
  }

  char buf[64];
  long total = 0, multi = 0, committed = 0;

  while (fgets(buf, sizeof buf, stdin)) {
    char *nl = strpbrk(buf, "\r\n");
    if (nl) *nl = 0;
    if (!buf[0]) continue;

    rime->clear_composition(session);
    for (const char *p = buf; *p; ++p) {
      rime->process_key(session, (int)(unsigned char)*p, 0);
    }

    RIME_STRUCT(RimeCommit, commit);
    if (rime->get_commit(session, &commit)) {
      ++committed;
      rime->free_commit(&commit);
    }

    RIME_STRUCT(RimeContext, ctx);
    if (rime->get_context(session, &ctx)) {
      ++total;
      if (ctx.menu.num_candidates > 1) {
        ++multi;
        printf("MULTI\t%s\t%d\t", buf, ctx.menu.num_candidates);
        for (int i = 0; i < ctx.menu.num_candidates; ++i) {
          printf("%s%s", i ? "|" : "", ctx.menu.candidates[i].text);
        }
        printf("\n");
      }
      rime->free_context(&ctx);
    }
    rime->clear_composition(session);
  }

  printf("TOTAL=%ld MULTI=%ld COMMITTED=%ld\n", total, multi, committed);

  rime->destroy_session(session);
  rime->finalize();
  return 0;
}

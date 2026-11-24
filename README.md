# DMIT LAX.AS3.Pro.TINY 补货微信通知

只监控 **LAX.AS3.Pro.TINY**（Premium，PID **253**，$10.90/月），不监控 EB 版本。

- GitHub Actions 每 5 分钟计划运行一次（GitHub **不保证准时执行**，可能延迟或跳过）。
- 从第三方库存页 https://vpsrestock.com/dmit/ 读取套餐状态。数据不是 DMIT 官方实时库存，页面改版时也可能识别失败。
- 当首次检测到现货或从缺货变成现货时，通过 Server酱发送微信消息；状态不变时不重复发送。
- 检测失败、数据过期或格式不符时视为 unknown，绝不猜测有货；连续 6 次失败后发送异常提醒（每天最多一次）。
- 通知包含官方下单链接：https://www.dmit.io/cart.php?a=add&pid=253
- 不自动购买，也不需要 DMIT 登录信息。

## 启用步骤

1. 将仓库切换成 **Public**：Settings → General → Danger Zone → Change repository visibility。公开仓库里的代码所有人都能看到，请勿把密钥写在文件里。
2. 打开 Settings → Secrets and variables → Actions → **New repository secret**。名称填 `SERVERCHAN_SENDKEY`，值粘贴 Server酱后台的 SendKey，保存。密钥不要发到聊天或写入仓库。
3. 打开 Settings → Actions → General → Workflow permissions，选择 **Read and write permissions** 后保存。这样工作流才能把库存状态写入 `stock_state.json`，实现跨次运行去重。
4. 进入 Actions → **DMIT Pro TINY Restock Monitor** → Run workflow，首次将 `send_test` 勾选 true，点击运行。检查是否收到微信测试消息。
5. 再手动运行一次，`send_test` 保持 false，确认库存检测无报错，并检查 `stock_state.json` 是否生成。之后每 5 分钟计划检查一次。
6. 订阅完成不代表已成功通知；务必检查 Actions 运行记录及微信测试。若无日志或失败，请先查 Actions 是否启用、Secrets 是否正确、权限是否允许提交状态文件。

## 通知方式

支持两种 Server酱 SendKey：

- 以 `SCT` 开头的 Turbo 密钥 → `sctapi.ftqq.com`
- 以 `sctp` 开头的 Server酱³ 密钥 → 用户专属 `push.ft07.com` 推送端点

注意微信接收渠道需要在 Server酱后台正确绑定，且可能有推送额度限制。

## 开发和测试

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
# 在本机的环境变量中设置 SERVERCHAN_SENDKEY，勿写入仓库
python dmit_watch.py --test
python dmit_watch.py
```

## 注意

使用 GitHub Actions 公共仓库的标准 GitHub 托管运行器通常无需付费计算分钟数，但适用 GitHub 平台政策和资源限制。定时任务可能延误，长期无活动也可能被停用。第三方库存提醒仅供参考；官方页面显示可下单才算确认补货。

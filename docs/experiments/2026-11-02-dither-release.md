# Dither 文档与实验发布验证

本次将校准工作的六个提交整理到 `codex/dither-mechanisms`，基于
`upstream/main` 的 `cd72061`。没有带入原工作分支的学习笔记或子模块历史。
入口是 [Dither总览](../../python/src/adctoolbox/examples/11_calibration/DITHER_GUIDE.md)，
本批结果见 [架构实验](2026-11-02-pn-architectures.md)，定点联合校准见
[HDC实验](2026-11-02-hdc-fixed.md)。

## 内容和边界

- 保留增益跟踪、独立机制、前台/后台混合、联合辨识诊断、定点HDC及架构实验，共九个示例入口。
- 新架构实验统一采用三路等权PN，峰值0.2；旧实验保留原激励和历史结果。
- Pipeline、SAR、TI、Delta-sigma分别说明注入节点、可观察量、辨识式、校正路径及失败控制。
- HDC定点结果有算术和逻辑资源约定；SAR/TI/Delta-sigma新增案例属于浮点行为模型，未完成RTL或晶体管验证。
- 发布分支包含此前已经实现的前台校准和增益跟踪API；本批HDC/架构实验仍只作为示例，没有增加通用Dither校准API。
- 保留五次项混叠、非线性记忆、非同样本双转换、无斜率/后置探针、错误扣除和闲置音残留等失败证据。

## 发布分支回归

在独立工作树的 `python/` 下运行：

```powershell
uv run --with pytest --with numba python -m pytest tests/unit/test_dither_background_example.py tests/unit/test_dither_mechanisms.py tests/unit/test_calibration_workflows.py tests/unit/test_joint_dither.py tests/unit/test_joint_dither_convergence.py tests/unit/test_hdc_fixed.py tests/unit/test_pn_architectures.py tests/unit/test_skill_cli.py tests/integration/test_user_guide_skill_examples.py -q -rs
```

结果：**109通过、1跳过、2警告，54.04秒**。唯一跳过项是当前Windows进程没有创建目录符号链接的权限，复制安装测试已通过。两条警告来自既有示例中只迭代一次的正弦频率拟合。确认导入路径属于发布工作树；环境为Python 3.13.1、NumPy 2.4.3、SciPy 1.17.1、Numba 0.68.1。

捆绑技能只向临时目录复制安装，状态检查为 `installed: yes, mode: copy, synced: yes`，没有修改用户的实际技能目录。

Sphinx使用 `-b html -q -W` 构建成功，没有警告。网页中的Dither指南直接包含打包示例的规范文档，避免另维护一套公式。顺带修复了既有 `analyze_error_spectrum` 返回值列表缺少空行的问题；该处只改文档格式，没有数值改动。

## 安装包验证

从发布工作树构建wheel和sdist，保留当前开发版本号0.9.1，没有执行PyPI发布。归档检查确认包含新文档和脚本，不含 `output/`、`.pyc`、`.nbi` 或 `.nbc` 产物。五个正式架构实验源文件在发布工作树、wheel、sdist中均与实验审计SHA-256一致；限定范围的Git LF规则避免Windows检出改变这些源文件字节。

| 本地构建产物 | 字节数 | SHA-256 |
|---|---:|---|
| adctoolbox-0.9.1-py3-none-any.whl | 459656 | `5360b9fb05973a19e37d9b1bedb42a24d92ea32eb5ac18c9a8ce9573c561c773` |
| adctoolbox-0.9.1.tar.gz | 321698 | `c92233604323b878eb95e0e111036d9cab43f4d81bd251c61ac951a378fc3924` |

归档时间戳可能让重新构建的整个包哈希不同；数值复核应使用实验审计中的逐源文件哈希。构建包保存在本机 `agent_playground/dither-dist-final-20261102/`，不作为仓库二进制附件提交。

另建不使用editable安装的独立虚拟环境，只安装上述wheel及其必需依赖，**不安装Numba**。确认导入来自该环境的 `site-packages`，通过 `adctoolbox-get-examples` 复制示例后运行：

```powershell
python adctoolbox_examples/11_calibration/exp_cal09_pn_architectures.py --quick --seeds 44 --output architecture-smoke
```

11个案例全部完成，生成CSV、JSON和图表，运行记录中的源文件哈希检查为true，实验主体用时3.41秒。该环境使用NumPy 2.5.4、SciPy 1.18.1；结果仅证明无可选加速时的安装和执行路径，不替代正式长记录收敛结果。wheel自带的技能也在临时目录复制安装，状态检查为synced。

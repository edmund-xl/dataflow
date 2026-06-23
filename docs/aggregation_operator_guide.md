# 中文版本

# 数据汇总与出包流程工程白皮书

## 摘要

本文面向数据汇总负责人，说明如何通过脚本合并多个采集包并生成完整 Dataflow Project 数据流图交付包。该流程将去重、冲突识别、质量校验、图模型构建、分层图生成、报告生成和压缩归档交给智能体完成，使汇总负责人只需要关注冲突确认和最终验收。

## 关键词

数据汇总；采集包合并；冲突报告；数据流图；交付包；自动出包。

## 一、适用范围

本文适用于需要接收多份 DCP 并生成最终交付包的数据汇总负责人。该流程不要求数据汇总负责人手工合并表格、手工修图或手工整理报告。

## 二、单个采集包出包方法

当只有一个采集包需要出包时，在项目根目录执行：

```bash
scripts/build_dataflow_package.sh path/to/DCP_v0.1
```

默认输出目录为：

```text
path/to/DCP_v0.1/dist/
```

输出包括完整交付目录和压缩归档。

## 三、多个采集包合并方法

当存在多个采集包时执行：

```bash
scripts/merge_dcp.sh path/to/DCP_source_a path/to/DCP_source_b path/to/DCP_source_c
```

默认输出目录为：

```text
dist/
```

系统会生成合并工作簿、合并报告、完整交付目录和压缩归档。

## 四、冲突处理方法

相同主键且内容一致的记录会自动去重。相同主键但内容不一致的记录会进入合并报告。智能体默认保留首次出现的记录用于后续产物生成，但汇总负责人必须在最终验收前检查并处理冲突。

## 五、输出结构

合并后的主要输出如下：

```text
dist/
  merged_dcp_<version>/
    dataflow_collection_template_v0.1.xlsx
    merge_report.xlsx
    merge_report.json
  dataflow_package_<version>/
  dataflow_package_<version>.zip
```

## 六、版权与授权

本项目版权归属 edmund-xl，并采用保留全部权利的私有授权。未经 edmund-xl 事先书面许可，不得复制、修改、分发或商用。完整授权文本见仓库根目录 `LICENSE` 文件。

## 七、结论

该流程将多源数据汇总变成可重复执行的脚本化操作。汇总负责人不再承担机械整理工作，而是聚焦数据冲突、风险确认和最终验收。

## 八、不可变规则

如果合并后的图或报告存在错误，应修正源工作簿或合并工作簿后重新运行脚本，不应手工修改生成产物。

---

# English Version

# Data Aggregation And Package Generation Engineering White Paper

## Abstract

This document is for the data aggregation owner and explains how to merge multiple collection packages and generate the complete Dataflow Project data-flow deliverable with scripts. The workflow delegates de-duplication, conflict detection, quality validation, graph construction, layered diagram rendering, report generation, and archive creation to the agent, so the owner can focus on conflict review and final acceptance.

## Keywords

Data aggregation; collection package merge; conflict report; data flow diagram; delivery package; automated package generation.

## 1. Scope

This document applies to the data aggregation owner who receives multiple DCPs and produces the final delivery package. The workflow does not require manual spreadsheet merging, manual diagram editing, or manual report assembly.

## 2. Build One Collection Package

When only one collection package needs to be built, run the following command from the project root:

```bash
scripts/build_dataflow_package.sh path/to/DCP_v0.1
```

The default output directory is:

```text
path/to/DCP_v0.1/dist/
```

The output includes the complete delivery directory and a compressed archive.

## 3. Merge Multiple Collection Packages

When multiple collection packages exist, run:

```bash
scripts/merge_dcp.sh path/to/DCP_source_a path/to/DCP_source_b path/to/DCP_source_c
```

The default output directory is:

```text
dist/
```

The system generates a merged workbook, a merge report, a complete delivery directory, and a compressed archive.

## 4. Conflict Handling

Rows with the same primary key and identical content are de-duplicated automatically. Rows with the same primary key but different content are recorded in the merge report. The agent keeps the first row for downstream artifact generation by default, but the data aggregation owner must review and resolve conflicts before final acceptance.

## 5. Output Structure

The main merged outputs are:

```text
dist/
  merged_dcp_<version>/
    dataflow_collection_template_v0.1.xlsx
    merge_report.xlsx
    merge_report.json
  dataflow_package_<version>/
  dataflow_package_<version>.zip
```

## 6. Copyright And License

This project is proprietary to edmund-xl and all rights are reserved. No copying, modification, distribution, or commercial use is permitted without prior written permission from edmund-xl. The full license text is available in the repository root `LICENSE` file.

## 7. Conclusion

This workflow turns multi-source aggregation into a repeatable scripted operation. The data aggregation owner no longer performs mechanical assembly and can focus on data conflicts, risk confirmation, and final acceptance.

## 8. Invariant Rule

If a generated diagram or report is wrong after merging, correct the source workbook or merged workbook and rerun the script. Do not manually edit generated artifacts.

# CC0 标准模板来源

本目录选取了 [pjm4github/FloorPlanner](https://github.com/pjm4github/FloorPlanner) 的 10 个俯视图符号，覆盖床、沙发、餐桌椅、洁具、电箱、电梯和楼梯。

- 上游目录：`assets/furnishings/`
- 上游许可：CC0 1.0 Universal（见 `LICENSE`）
- 原始单位：英寸；导入语义 JSON 时转换为整数毫米
- 使用方式：项目 JSON 只打包实际使用的模板，运行时不依赖本目录或外部网址

这些文件是标准库种子，不参与现有 CAD 回归样例的几何复原；现有图中的匿名 CAD 块会转换为项目私有模板。

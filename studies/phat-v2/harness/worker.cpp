// Benchmark adapter only. PHAT headers and algorithms are used unchanged.
#include <phat/compute_persistence_pairs.h>
#include <phat/algorithms/standard_reduction.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using Matrix = phat::boundary_matrix<phat::bit_tree_pivot_column>;
using Clock = std::chrono::steady_clock;
struct Input { std::vector<int> dims, grades; std::vector<phat::column> columns; };
struct Answer { std::vector<std::array<int,3>> finite; std::vector<std::array<int,2>> essential; };

Input read_input(const std::string& path) {
    std::ifstream stream(path);
    size_t n; if (!(stream >> n)) throw std::runtime_error("cannot read input");
    Input f; f.dims.resize(n); f.grades.resize(n); f.columns.resize(n);
    for (size_t i=0; i<n; ++i) {
        size_t count;
        if (!(stream >> f.dims[i] >> f.grades[i] >> count)) throw std::runtime_error("truncated input");
        f.columns[i].resize(count);
        for (auto& row : f.columns[i]) {
            if (!(stream >> row) || row < 0 || row >= phat::index(i)) throw std::runtime_error("bad boundary");
        }
        if (!std::is_sorted(f.columns[i].begin(), f.columns[i].end()) ||
            std::adjacent_find(f.columns[i].begin(), f.columns[i].end()) != f.columns[i].end())
            throw std::runtime_error("noncanonical column");
    }
    std::string excess; if (stream >> excess) throw std::runtime_error("trailing data");
    return f;
}

std::unique_ptr<Matrix> construct(const Input& f) {
    auto m = std::make_unique<Matrix>();
    if (m->get_num_cols() != 0) throw std::runtime_error("constructor retained columns");
    m->set_num_cols(f.dims.size());
    for (size_t i=0; i<f.dims.size(); ++i) { m->set_dim(i, f.dims[i]); m->set_col(i, f.columns[i]); }
    return m;
}

bool pristine(const Matrix& m, const Input& f) {
    if (m.get_num_cols() != phat::index(f.dims.size())) return false;
    phat::column col;
    for (size_t i=0; i<f.dims.size(); ++i) {
        m.get_col(i, col);
        if (m.get_dim(i) != f.dims[i] || col != f.columns[i]) return false;
    }
    return true;
}

Answer query(Matrix& m, const Input& f, bool standard) {
    phat::persistence_pairs pairs;
    if (pairs.get_num_pairs() != 0) throw std::runtime_error("pairs retained");
    if (standard) phat::compute_persistence_pairs<phat::standard_reduction>(pairs, m);
    else phat::compute_persistence_pairs<phat::twist_reduction>(pairs, m);
    Answer out;
    std::vector<bool> paired(f.dims.size(), false);
    for (phat::index i=0; i<pairs.get_num_pairs(); ++i) {
        auto [b, d] = pairs.get_pair(i);
        if (b<0 || b>=d || d>=phat::index(f.dims.size()) || paired[b] || paired[d] ||
            f.dims[d] != f.dims[b]+1 || f.grades[b] > f.grades[d])
            throw std::runtime_error("invalid PHAT pair");
        // Mark zero-length pairs too: otherwise they become false essentials.
        paired[b]=true; paired[d]=true;
        if (f.grades[b] != f.grades[d]) out.finite.push_back({f.dims[b],f.grades[b],f.grades[d]});
    }
    for (size_t i=0; i<f.dims.size(); ++i)
        if (!paired[i]) out.essential.push_back({f.dims[i],f.grades[i]});
    std::sort(out.finite.begin(),out.finite.end()); std::sort(out.essential.begin(),out.essential.end());
    return out;
}

template<size_t N> void print_array(const std::vector<std::array<int,N>>& values) {
    std::cout << '[';
    for (size_t i=0; i<values.size(); ++i) {
        if(i) std::cout << ','; std::cout << '[';
        for (size_t j=0; j<N; ++j) { if(j) std::cout << ','; std::cout << values[i][j]; }
        std::cout << ']';
    }
    std::cout << ']';
}
void print_answer(const Answer& a) {
    std::cout << "{\"finite\":"; print_array(a.finite);
    std::cout << ",\"essential\":"; print_array(a.essential); std::cout << '}';
}

int main(int argc, char** argv) {
    try {
        if (argc!=6) throw std::runtime_error("usage: worker list.tsv correctness|timing samples warmups twist|standard");
        const bool timing=std::string(argv[2])=="timing", standard=std::string(argv[5])=="standard";
        const int samples=std::stoi(argv[3]), warmups=std::stoi(argv[4]);
        std::cout.precision(17);
        std::cout << "{\"event\":\"metadata\",\"tool\":\"phat\",\"compiler\":\"" << __VERSION__
                  << "\",\"algorithm\":\"" << (standard ? "standard" : "twist")
                  << "\",\"representation\":\"bit_tree_pivot_column\",\"clock_steady\":"
                  << (Clock::is_steady ? "true" : "false") << "}" << std::endl;
        // Negative reset control: equality must reject a modified native matrix.
        Input control{{0,0,1},{0,0,1},{{},{},{0,1}}};
        auto probe=construct(control); probe->clear(2);
        if(pristine(*probe,control)) throw std::runtime_error("reset guard accepts changed columns");
        std::cout << "{\"event\":\"reset_guard\",\"passed\":true}" << std::endl;
        probe.reset();
        std::ifstream list(argv[1]); if(!list) throw std::runtime_error("missing list");
        std::string line;
        while(std::getline(list,line)) {
            auto tab=line.find('\t'); if(tab==std::string::npos) throw std::runtime_error("bad list");
            const auto id=line.substr(0,tab); const Input f=read_input(line.substr(tab+1));
            std::vector<std::string> phases=timing ? std::vector<std::string>{"construction","query","combined"} : std::vector<std::string>{"query"};
            for (const auto& phase : phases) {
                const int count=timing ? warmups+samples : 1;
                for(int iteration=0; iteration<count; ++iteration) {
                    std::cout << "{\"event\":\"begin\",\"case\":\""<<id<<"\",\"phase\":\""<<phase<<"\"}" << std::endl;
                    std::unique_ptr<Matrix> m;
                    if(phase=="query") { m=construct(f); if(!pristine(*m,f)) throw std::runtime_error("reset failed"); }
                    Answer answer;
                    const auto start=Clock::now();
                    if(phase!="query") m=construct(f);
                    if(phase!="construction") answer=query(*m,f,standard);
                    const auto end=Clock::now();
                    if(phase=="construction" && !pristine(*m,f)) throw std::runtime_error("construction failed");
                    std::cout << "{\"event\":\"sample\",\"case\":\""<<id<<"\",\"phase\":\""<<phase
                              <<"\",\"kind\":\""<<(!timing ? "correctness" : iteration<warmups ? "warmup" : "measurement")
                              <<"\",\"iteration\":"<<iteration<<",\"reset_verified\":true,\"seconds\":";
                    if(timing) std::cout<<std::chrono::duration<double>(end-start).count(); else std::cout<<"null";
                    std::cout<<",\"compile_seconds\":0,\"recompile_seconds\":0,\"allocation_bytes\":null,\"retained_input_bytes\":null,\"answer\":";
                    if(phase=="construction") std::cout<<"null"; else print_answer(answer);
                    std::cout<<'}'<<std::endl;
                    // m, answer and all reduction state die before the next request.
                }
            }
        }
        std::cout << "{\"event\":\"complete\"}" << std::endl;
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
